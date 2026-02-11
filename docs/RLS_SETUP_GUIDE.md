# Установка RLS (Row Level Security) и Ролей в Supabase

**Дата:** 11 февраля 2026
**Статус:** Готово к внедрению
**Проблема:** Database Linter报告 - RLS отключена на 7 таблицах

## Проблема

Supabase Database Linter обнаружил, что на следующих таблицах в `public` схеме отключена Row Level Security (RLS):

1. `news_channels`
2. `news_digest_posts`
3. `competitor_tg_posts`
4. `news_posts`
5. `news_post_categories`
6. `news_digests`
7. `news_categories`

Это критическая проблема безопасности, т.к. без RLS любой авторизованный пользователь может читать/менять **все данные** во всех таблицах.

## Архитектура решения

### 1. Модель доступа (на основе CLAUDE.md)

**Роли пользователей:**
- `viewer` - может читать все данные (по умолчанию)
- `admin` - может читать, создавать, менять и удалять данные в справочниках

**Принцип:**
- Это **витрина** - все пользователи видят одинаковые данные
- Нет приватных данных пользователей
- Админы управляют справочниками (конкуренты, группы, категории новостей, каналы)

### 2. Реализация

**Компоненты:**

1. **Таблица `public.users`** - добавлена колонка `role`
   - Хранит роль пользователя (admin/viewer)
   - Заполняется вручную при создании пользователя в БД

2. **Auth Metadata** - `user_role` в JWT токене
   - Когда пользователь логинится, роль из БД устанавливается в auth metadata
   - Суть: `supabase.auth.updateUser({ data: { user_role: 'admin' } })`
   - JWT токен получает это значение в поле `user_metadata`

3. **RLS Политики** - контролируют доступ
   - `SELECT` - доступен всем (USING (true))
   - `INSERT/UPDATE/DELETE` - только для админов (USING (is_admin()))
   - Функция `is_admin()` проверяет `auth.jwt() ->> 'user_metadata'` → 'user_role'

## План внедрения

### Шаг 1: Запустить миграции в Supabase

1. **Откройте Supabase Dashboard**
   - Project → SQL Editor

2. **Выполните первую миграцию** `setup_user_roles.sql`
   ```sql
   -- Добавляет колонку 'role' в таблицу public.users
   -- Проверяет что она существует
   ```

3. **Выполните вторую миграцию** `enable_rls_all_tables_v2.sql`
   ```sql
   -- Включает RLS на всех таблицах
   -- Создаёт функцию is_admin()
   -- Создаёт политики доступа
   ```

### Шаг 2: Проверить структуру БД

Убедитесь что колонка `role` добавлена:

```sql
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
AND table_name = 'users'
ORDER BY ordinal_position;
```

Должны быть колонки:
- `id` (uuid)
- `telegram_id` (bigint)
- `telegram_username` (text)
- `display_name` (text)
- `role` (text) ← **должна быть!**
- `last_seen_at` (timestamp)
- `created_at` (timestamp)

### Шаг 3: Обновить код приложения

Код уже обновлён в `webapp/src/services/supabase.js`:

```javascript
export async function checkUserAccess(telegramUser) {
  // ... получаем пользователя из БД ...
  
  // ← НОВОЕ: устанавливаем роль в auth metadata
  const userRole = data.role || 'viewer'
  const { error: updateError } = await supabase.auth.updateUser({
    data: { user_role: userRole }
  })
  
  // ... обновляем last_seen_at ...
  return { allowed: true, user: data }
}
```

### Шаг 4: Назначить роли пользователям

Откройте Supabase Dashboard → Database → `public.users` таблица

Обновите роли существующих пользователей:

```sql
-- Админ
UPDATE public.users SET role = 'admin' WHERE telegram_id = YOUR_ADMIN_TELEGRAM_ID;

-- Обычные пользователи
UPDATE public.users SET role = 'viewer' WHERE telegram_id != YOUR_ADMIN_TELEGRAM_ID;
```

### Шаг 5: Проверить RLS Политики

В Supabase Dashboard:
1. Database → RLS Policies
2. Для каждой таблицы должны быть политики:
   - "Allow all users to read {table_name}" (SELECT)
   - "Allow admins to manage {table_name}" (INSERT/UPDATE/DELETE)

### Шаг 6: Тестировать

**Тестовый сценарий 1 (Viewer):**
1. Залогиниться как обычный пользователь (role = 'viewer')
2. ✅ Можете читать все данные
3. ❌ Не можете добавлять/менять конкурентов (получите ошибку RLS)

**Тестовый сценарий 2 (Admin):**
1. Залогиниться как админ (role = 'admin')
2. ✅ Можете читать все данные
3. ✅ Можете добавлять/менять/удалять конкурентов

## Диагностика проблем

### Проблема: "JWT missing" или ошибка при доступе к данным

**Решение:**
1. Убедитесь что пользователь зарегистрирован в `public.users`
2. Проверьте что `checkUserAccess()` вызывается перед доступом к данным
3. В браузере откройте DevTools → Console → посмотрите логи

```javascript
// Debug: посмотрите что возвращает auth.updateUser()
console.log('Auth user:', await supabase.auth.getUser())
```

### Проблема: Админ не может добавить конкурента (RLS блокирует)

**Решение:**
1. Проверьте что в `public.users` таблице стоит role = 'admin' для этого пользователя
2. Проверьте что `supabase.auth.updateUser()` успешно выполнился в `checkUserAccess()`
3. В Supabase SQL Editor выполните:
   ```sql
   SELECT auth.jwt() ->> 'user_metadata';
   -- Должен содержать: {"user_role":"admin"}
   ```

### Проблема: "Policy evaluation error"

**Решение:**
1. Функция `is_admin()` может не существовать
2. Повторно запустите миграцию `enable_rls_all_tables_v2.sql`
3. Проверьте что функция создана:
   ```sql
   SELECT exists (
     SELECT 1 FROM pg_proc WHERE proname = 'is_admin'
   );
   ```

## Файлы изменений

### Созданы:
- `migrations/setup_user_roles.sql` - добавляет колонку role
- `migrations/enable_rls_all_tables_v2.sql` - включает RLS и создаёт политики

### Обновлены:
- `webapp/src/services/supabase.js` - функция `checkUserAccess()`

## Документация

- **Supabase RLS:** https://supabase.com/docs/guides/database/postgres/row-level-security
- **JWT Claims:** https://supabase.com/docs/guides/auth/custom-claims
- **Database Linter:** https://supabase.com/docs/guides/database/database-linter

## Временная шкала

- ✅ 11.02.2026 - Создано решение
- ⏳ TODO - Запустить миграции
- ⏳ TODO - Протестировать в staging
- ⏳ TODO - Развернуть в production
