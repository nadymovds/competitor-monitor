# RLS Setup - Quick Start

## ⚡ 5 шагов для быстрого внедрения

### 1. Запустите миграции в Supabase SQL Editor

**Сначала:**
```sql
-- Copy & Paste: migrations/setup_user_roles.sql
```

**Затем:**
```sql
-- Copy & Paste: migrations/enable_rls_all_tables_v2.sql
```

### 2. Проверьте таблицу users

```sql
SELECT * FROM public.users LIMIT 1;
```

Должна быть колонка `role` (возможно со значением NULL).

### 3. Установите роли

```sql
-- Админ
UPDATE public.users SET role = 'admin' WHERE telegram_id = 457121917;

-- Остальные
UPDATE public.users SET role = 'viewer' WHERE role IS NULL;
```

### 4. Проверьте RLS Policy

В Supabase Dashboard:
- Database → RLS Policies
- Откройте таблицу `news_channels`
- Должны быть 4 политики (SELECT, INSERT, UPDATE, DELETE)

### 5. Тестируйте!

В браузере:
- Откройте приложение
- F12 → Console
- Попробуйте добавить конкурента (как админ)
- Должно работать! ✅

## 🐛 Если не работает

```javascript
// В консоли браузера:
const { data } = await supabase.auth.getUser()
console.log('User metadata:', data.user.user_metadata)
// Должно быть: { user_role: 'admin' }
```

Если нет `user_role` - значит не запустилась миграция или БД не обновилась.

## 📚 Полная документация

→ Читайте: `docs/RLS_SETUP_GUIDE.md`
