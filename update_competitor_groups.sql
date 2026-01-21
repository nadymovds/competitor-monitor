-- =============================================================================
-- СКРИПТ ОБНОВЛЕНИЯ ГРУПП КОНКУРЕНТОВ
-- Запустите этот скрипт в SQL Editor Supabase
-- =============================================================================

-- Шаг 1: Создаем временную таблицу с данными из файла
CREATE TEMP TABLE csv_competitors (
    name TEXT,
    website TEXT,
    categories TEXT[]
);

INSERT INTO csv_competitors (name, website, categories) VALUES
('SKAI', 'https://skai.online/company/', ARRAY['вендор', 'интегратор']),
('Форт-Телеком', 'https://www.fort-telecom.ru/', ARRAY['вендор']),
('NAVITEL', 'https://navitel.ru/ru', ARRAY['вендор']),
('Автограф', 'https://glonassgps.com/', ARRAY['вендор']),
('Омникомм', 'https://www.omnicomm.ru/', ARRAY['вендор']),
('ГЛОНАСС Софт', 'https://glonasssoft.ru/', ARRAY['вендор']),
('Карвис', 'https://carvis.org/', ARRAY['вендор']),
('Навтелеком', 'https://navtelecom.ru/ru/', ARRAY['вендор']),
('Вега абсолют', 'https://vega-absolute.ru/', ARRAY['вендор']),
('ГалилеоСкай', 'https://galileosky.ru/', ARRAY['вендор']),
('КСОР', 'https://xor-group.ru/', ARRAY['вендор']),
('ОКО системс', 'https://oko-systems.ru/', ARRAY['вендор']),
('Гдемои', 'https://www.gdemoi.ru/', ARRAY['вендор']),
('Гарвекс', 'https://garveks.ru/', ARRAY['вендор']),
('Телтоника', 'https://teltonika-monitoring.ru/', ARRAY['вендор']),
('Автосенсор', 'https://avtosensor.ru/', ARRAY['вендор']),
('Эскорт', 'https://www.fmeter.ru/', ARRAY['вендор']),
('Нейроком', 'https://neurocom.ru/', ARRAY['вендор']),
('Интеллико', 'https://intelliko.ru/', ARRAY['вендор']),
('Видеомобиль', 'https://videomobil.su/', ARRAY['вендор']),
('ООО «ЦИТ БАРС»', 'https://globars.ru/', ARRAY['вендор']),
('ООО "ЛОКАРУС"', 'https://site.locarus.ru/', ARRAY['вендор']),
('ООО "УМНАЯ ЛОГИСТИКА"', 'https://ul.su/', ARRAY['вендор']),
('ООО «В1-ТЕХНОЛОДЖИ»', 'https://v1tech.ru', ARRAY['вендор']),
('ООО «ГелиосСофт»', 'https://www.geliossoft.ru/', ARRAY['вендор']),
('NVI Solutions', 'https://nvi-solutions.ru/', ARRAY['вендор']),
('NSCAR', 'https://nscar.ru/', ARRAY['вендор']),
('Протон М', 'https://proton-m.com/', ARRAY['вендор']),
('Sowa', 'https://www.sowa.pro/', ARRAY['вендор']),
('ООО «МЕДИКУМ»', 'https://mdcm.ru/', ARRAY['телемедицина']),
('ООО «Нобилис»', 'https://nobilis-tm.ru/', ARRAY['телемедицина']),
('ООО «Линия МедКонтроля»', 'https://medmap24.ru/', ARRAY['телемедицина']),
('ООО «Медоператор»', 'https://medoperator.org/', ARRAY['телемедицина']),
('ООО «БИОСОФТ-ПМО»', 'https://biosoft.ltd/', ARRAY['телемедицина']),
('ООО «Смарт-технологии»', 'https://smart-tehnologies.ru/', ARRAY['телемедицина']),
('АО «Технология здоровья»', 'https://medcontrol.cloud/', ARRAY['телемедицина']),
('ООО «Арциус»', 'https://medpoint24.ru/', ARRAY['телемедицина']),
('ООО «ЕвроМедХолдинг»', 'https://emh24.ru/', ARRAY['телемедицина']),
('ООО «ПрМедика»', 'https://medosmotry.com/', ARRAY['телемедицина']),
('ООО «ТМС 77»', 'https://fortcross.ru/', ARRAY['телемедицина']),
('ООО «Пульс»', 'https://предрейсовый-медосмотр.рф/', ARRAY['телемедицина']),
('ООО МЦ «Сибирское здоровье»', 'https://сибирка.com/', ARRAY['телемедицина']),
('ООО «Айтимед»', 'https://itmed.online/', ARRAY['телемедицина']),
('ООО «МедХаб»', 'https://medhab.ru/', ARRAY['телемедицина']),
('ООО МЦ «ПРОФМЕД»', 'https://profmed38.ru/', ARRAY['телемедицина']),
('ООО «Зеница-Урал»', 'https://zenizaural.ru/', ARRAY['телемедицина']),
('ООО «Тахонетсофт»', 'http://tahonetsoft.ru/', ARRAY['телемедицина']),
('ООО «Тетрон Мед»', 'https://tetronmed.ru/', ARRAY['телемедицина']),
('ООО «Тетрон»', 'https://tetron.ru/', ARRAY['вендор']),
('ООО «АФЕЗИС»', 'https://афезис.рф/', ARRAY['телемедицина']),
('ООО «МАССИВ»', 'https://avtomedik.ru/', ARRAY['телемедицина']),
('ООО «Богатырь»', 'https://bogatyrmed.orgs.biz/', ARRAY['телемедицина']),
('ООО «ЦПМО»', 'https://ckpt-orientir.ru/', ARRAY['телемедицина']),
('ООО «БизнесПрофСервис»', 'https://bps14.ru/', ARRAY['телемедицина']),
('ООО «Промышленная Медицина»', 'https://i-med.pro/', ARRAY['телемедицина']),
('ООО «Медпроф»', 'https://предрейсовые-осмотры.рф/', ARRAY['телемедицина']),
('ООО «Медум»', 'https://www.medym.ru/', ARRAY['телемедицина']),
('ЧУЗ «КБ «РЖД-Медицина» г. Санкт-Петербурга»', 'https://rzd-medicine.ru/', ARRAY['телемедицина']),
('ООО «Автомед»', 'https://avtomedpnz.ru/', ARRAY['телемедицина']),
('ООО «Приоритет»', 'https://predreys78.ru/', ARRAY['телемедицина']),
('ООО «ММЦ Профмедицина»', 'https://www.groupmmc.ru/', ARRAY['телемедицина']),
('ООО «Телеосмотр»', 'https://teleosmotr.ru/', ARRAY['телемедицина']),
('ООО «КПЛПЗ «ЕМС»', 'https://www.emsclinic.ru/', ARRAY['телемедицина']),
('ООО «АлкоМед»', 'https://алкомед-предрейсовый.рф', ARRAY['телемедицина']),
('ООО «Каракум»', 'https://врейс.рф/', ARRAY['телемедицина']),
('ООО «ДМК № 1»', 'https://dmk1.ru/', ARRAY['телемедицина']),
('ООО «РТК-МедОператор»', '-', ARRAY['телемедицина']),
('ООО «ПРОмилле»', 'https://pro-mille.su/', ARRAY['телемедицина']),
('ООО «Центр Сервис»', 'https://centrservis44.ru/', ARRAY['телемедицина']),
('ООО «МедТехЗащита»', 'https://medtz.ru/', ARRAY['телемедицина']),
('ООО «АЛЛЕГРО М»', 'https://mto5.ru/', ARRAY['телемедицина']),
('ООО «Медицинские осмотры и комиссии»', '-', ARRAY['телемедицина']),
('ООО «АМУ Клиники Столицы»', 'https://stoclinic.ru/', ARRAY['телемедицина']),
('ООО «Регион-Медсервис»', 'https://remedservice.ru/', ARRAY['телемедицина']),
('ООО «Альбатрос»', 'https://albatros-med.ru/', ARRAY['телемедицина']),
('ООО «ЕКАМЕДТЕСТ»', 'https://ekamedtest.ru/', ARRAY['телемедицина']),
('ООО «ПРЕДРЕЙСОВЫЙ»', 'https://predrejsovyj.ru/', ARRAY['телемедицина']),
('ООО «Тест»', 'https://predreismo.ru/', ARRAY['телемедицина']),
('СКАУТ-РС', 'https://scout-gps.ru/', ARRAY['вендор', 'интегратор']),
('Ситипоинт', 'https://citypoint.ru/', ARRAY['вендор', 'интегратор']),
('NVI', 'https://exodrive.tech/', ARRAY['вендор', 'интегратор']),
('СпейсТим', 'https://www.space-team.com/', ARRAY['вендор', 'интегратор']),
('Монтранс', 'https://montrans.ru/', ARRAY['вендор', 'интегратор']),
('Тетрон', 'https://tetron.ru/', ARRAY['интегратор']),
('Global Position', 'https://globalposition.ru/', ARRAY['интегратор']),
('24telecom', 'https://24telecom.ru/', ARRAY['интегратор']),
('Глонасс-Восток', 'http://geast.ru/', ARRAY['интегратор']),
('ТИС онлайн', 'https://tis-online.com/', ARRAY['вендор']),
('Лидинг-Альянс', 'https://lacctv.ru/', ARRAY['вендор']),
('Ставтрэк', 'https://www.stavtrack.ru/', ARRAY['вендор', 'интегратор']),
('АЙТОБ', 'itob.ru', ARRAY['интегратор']),
('АО "АРКАН-М"', 'www.arkan-group.ru', ARRAY['интегратор']),
('ООО НПО "АТИС"', 'www.atis-control.ru', ARRAY['интегратор']),
('ООО "ГЛАДИУС ТРЕЙДИНГ"', 'micgladius.ru', ARRAY['интегратор']),
('ООО "ГЛОБАЛСАТ НАВИГАЦИЯ"', 'https://www.globalsat.ru/', ARRAY['интегратор']),
('ООО "ГЛОНАСС ЦЕНТР"', 'www.glonass-center.net', ARRAY['интегратор']),
('ООО "ГЛОНАСС-СЕРВИС"', 'glonasss.com', ARRAY['интегратор']),
('ООО "ГУГОЛ ПЛЮС"', 'https://gygol.ru/', ARRAY['интегратор']),
('ООО "ДИВИЗИОН СИСТЕМС"', 'https://kontrol-glonass.ru/', ARRAY['интегратор']),
('ООО "ИБС-АЛЬФА"', 'http://www.ibs-a.ru/', ARRAY['интегратор']),
('ООО "ИГЛИТ"', 'https://iglit.ru/', ARRAY['интегратор']),
('ООО ИНТЕРРА', '', ARRAY['интегратор']),
('ООО КОМПАНИЯ "ИТ-СЕРВИС"', 'http://www.it-service.ru', ARRAY['интегратор']),
('ООО "КОБРА-РОСТОВ"', 'gcsysmet.ru', ARRAY['интегратор']),
('ООО "КОМПАНИЯ СПЕЦАВТОМАТИКА"', 'avt2007.ru', ARRAY['интегратор']),
('ООО "КОМПАС ТЕЛЕКОМ"', 'https://com-pass.ru/', ARRAY['интегратор']),
('ООО "ЛУВ"', 'smartdriving.io', ARRAY['вендор', 'интегратор']),
('ООО "МЕГАПЕЙДЖ"', 'www.autolocator.ru', ARRAY['интегратор']),
('ООО "МОБИ ЛАЙН"', 'https://xn--80aahb8aeoedxja1a.xn--p1ai/', ARRAY['интегратор']),
('ООО "МОНИТОРИНГ-СЕРВИС"', '', ARRAY['интегратор']),
('ООО "МОНИТОРИНГАВТО"', 'https://www.monitoring-auto.ru/', ARRAY['интегратор']),
('АО "МЦМ"', 'www.mcem.ru', ARRAY['интегратор']),
('НАВИ ГРУПП', 'navi-group.ru', ARRAY['интегратор']),
('ООО "НАВИСАР"', 'navisar13.ru', ARRAY['интегратор']),
('ООО "НАВИСТЕК"', 'https://navistek.ru/', ARRAY['интегратор']),
('ООО "НАВИТРЕЙД"', 'navitrade.ru', ARRAY['интегратор']),
('ООО "НОВОСИБИРСКРЕФСЕРВИС"', 'www.gps54.ru', ARRAY['интегратор']),
('ООО "ПЛАТА-ТС"', 'www.plata-ts.ru', ARRAY['интегратор']),
('ООО "ПРЕТОРИЯ-КРЫМ"', 'http://pretoriacrimea.ru/', ARRAY['интегратор']),
('ООО "РЦМ "ПОДРАЗДЕЛЕНИЕ "Д"', 'dts-d.ru', ARRAY['интегратор']),
('ООО "РЭД ЛАЙН"', 'redline-scout.ru', ARRAY['интегратор']),
('ООО "С-ТЕЛЕКОМ"', 's-telecom.su', ARRAY['интегратор']),
('ООО "С.Т.С."', 'sts-51.ru', ARRAY['интегратор']),
('ООО "САНТЭЛ МОНИТОРИНГ"', 'suntel-nn.ru', ARRAY['интегратор']),
('ООО "СИБИРСКИЕ ИННОВАЦИОННЫЕ СИСТЕМЫ"', 'http://www.sibinn.ru/', ARRAY['интегратор']),
('ООО НПЦ "СИГНАЛ СЕРВИС"', 'https://tahograf76.ru/monitoring/', ARRAY['интегратор']),
('ООО "СИНЭРА"', 'syn-era.ru', ARRAY['интегратор']),
('ООО "СКАЙ ТЕЛЕКОМ"', 'http://skytelecom.su', ARRAY['интегратор']),
('ООО"СКАУТ-САМАРА"', '', ARRAY['интегратор']),
('ООО "СМАРТ М2М"', '', ARRAY['интегратор']),
('ООО "СМАРТ ПРОФИТ"', 'https://smartprofit.info/', ARRAY['интегратор']),
('ООО "СПУТНИК АВТО"', 'sputnik-avto.net', ARRAY['интегратор']),
('ООО "СПУТНИКСЕРВИС"', 'https://sputnik-service.com', ARRAY['интегратор']),
('ООО "СТС"', 'https://cevertransc.ru/', ARRAY['интегратор']),
('ООО "СФЕРА КОНТРОЛЯ"', 'www.sfera-k.ru', ARRAY['интегратор']),
('ООО "ТАМБОВНАВИГАЦИЯ"', 'tmbnavi.ru', ARRAY['интегратор']),
('ООО "ТЕХНОСИТИ"', 'http://tsyug.ru/#', ARRAY['интегратор']),
('ООО "ТК - ЦЕНТР"', 'https://tkglonass.ru', ARRAY['интегратор']),
('ООО "ТН-ГРУПП"', 'http://www.tn-group.net', ARRAY['интегратор']),
('ООО "ТТВКОМ"', 'https://ttwcome.ru/', ARRAY['интегратор']),
('ООО "УЛЬТРАСТАР-НКТ"', 'ultrastar-nkt.ru', ARRAY['интегратор']),
('ООО "ФОРТ СИСТЕМС"', 'http://fortsyst.ru/', ARRAY['интегратор']),
('ООО "ЭРКАС"', 'https://erkas.pro/', ARRAY['интегратор']),
('ООО "ЮСС"', 'ugrasmart.ru', ARRAY['интегратор']),
('ООО "Вёлд Телеком"', '', ARRAY['интегратор']),
('ООО "СМАРТ ТЕЛЕМАТИК ТЕХНОЛОДЖИ"', '', ARRAY['интегратор']),
('ООО "ЕНДС - ОРЕЛ"', '', ARRAY['интегратор']),
('ООО "ЕНДС - ФИЦ"', '', ARRAY['интегратор']),
('ООО "ЕНДС-ХМАО"', '', ARRAY['интегратор']),
('ООО "М2М ТЕЛЕМАТИКА ИВАНОВО"', 'https://glonass-iv.ru/', ARRAY['интегратор']),
('ООО "М2М ТЕЛЕМАТИКА РЯЗАНЬ"', 'https://m2m-rzn.ru/', ARRAY['интегратор']),
('ООО "М2М ТЕЛЕМАТИКА - АЛТАЙ"', 'm2m-altai.ru', ARRAY['интегратор']),
('ООО "ОМНИКОММ ДВ"', 'omnicommdv.ru', ARRAY['интегратор']),
('ООО "ОМНИКОММ СИСТЕМС"', 'https://omnicommsystems.ru/', ARRAY['интегратор']),
('ООО "ОМНИКОММ СТОЛИЦА"', 'https://sbsrus.ru/', ARRAY['интегратор']),
('ООО "ОМНИКОММ ТВЕРЬ"', 'https://www.omnicomm-tver.ru/', ARRAY['интегратор']),
('ООО "ОМНИКОММ-СПБ"', 'omnicommspb.ru', ARRAY['интегратор']),
('ООО "ОМНИКОММ-УРАЛ"', 'omnicomm-kuzbass.ru', ARRAY['интегратор']),
('ООО "ОМНИКОММ - ЦЕНТР"', 'https://omnicomm-center.ru/', ARRAY['интегратор']),
('ООО "ОМНИКОММ24"', 'https://omnicomm24.ru/', ARRAY['интегратор']),
('ООО "СИТИПОИНТ - ТВЕРЬ"', 'https://citypoint-tver.ru/', ARRAY['интегратор']),
('ООО "СКАУТ-СЕРВИС"', '', ARRAY['интегратор']),
('ООО "ТЕХНОКОМ-ОМСК"', 'tk-omsk.ru', ARRAY['интегратор']),
('ООО "НЕОМАТИКА"', 'www.neomatica.com', ARRAY['вендор']),
('ООО "ТД АРУСНАВИ"', 'https://arusnavi.ru/', ARRAY['вендор']),
('Геострон', 'https://geostron.ru/', ARRAY['вендор']),
('НАВСИ', 'https://navsy.ru/', ARRAY['вендор', 'интегратор']),
('Виалон-Сервис', 'https://wialon-service.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ГК АРСА', 'https://arsa.pro/', ARRAY['интегратор', 'второстепенный конкурент']),
('PSM Group', 'https://psm-group.com/', ARRAY['интегратор', 'второстепенный конкурент']),
('Траектория', 'https://glonassgps.biz/', ARRAY['интегратор', 'второстепенный конкурент']),
('ВЕком', 'https://vecom.su/', ARRAY['интегратор', 'второстепенный конкурент']),
('Аленсио', 'http://www.alensio-gps.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('Триви', 'https://trivi.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Эксперт Телематика', 'https://getgps.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Геосервис', 'https://geosmt.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Автоконнект', 'https://avt78.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('АВТОНАВИКС', 'https://avtonavix.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('АТК', 'https://atkweb.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Тахограф Мастер', 'http://tahografmaster.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ГЛОНАСС-ЮГРА', 'https://glonass86.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Автоскан', 'https://auto-scan.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('Цезарь', 'https://spb.csat.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "А-ЛАЙН"', 'а-лайн.рф', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АВТОПЕЛЕНГ"', 'http://peleng.tomsk.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АВТОСКАН-СЕРВИС"', 'https://ekb.avtoscan42.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АВТОТАХОГРАФ"', 'https://auto-tahograf.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АГМ"', 'http://aimonitoring.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АДС"', 'https://ads-glonass.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('НАВИ Т', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АНДРОМЕДА-ТЮМЕНЬ"', 'https://at-72.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АНТЕЙ-СЕРВИС"', 'asukontur.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АПЕКС"', 'http://apex26.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АРГУС-СЕРВИС"', 'bus44.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АРМО-СИСТЕМЫ"', 'lenel.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "БИЗНЕС-ДОК"', 'https://www.bd71.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "БИЗНЕС-НАВИГАЦИЯ"', 'https://spb.bnav.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "БОНДАРЬ КОНСАЛТИНГ"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ОМНИКОММ АВТО"', 'http://omnicommauto.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГЕО СИСТЕМ"', 'http://geo-s.net', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГК ФОРТОН"', 'https://forton24.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГЛОБАЛ МОНИТОРИНГ"', 'www.gm56.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГЛОНАВТ"', 'https://glonavt.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГЛОНАСС 35"', 'https://csc35.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГЛОНАСС СИСТЕМ"', 'https://glonasssystem.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО КОМПАНИЯ "ГЛОНАСС-12"', 'https://xn--12-6kcl4bmg0aa.xn--p1ai/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ГРАНД ВЭЙ"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ДВЦСМ"', 'bnav.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ДЕЛЬТА АВТО СИСТЕМС"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "КРИПТОТЕЛЕКОМ"', 'cryptotelecom.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "МСС"', 'mssglonass.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "МПС"', 'http://mpsvrn.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "МС ГРУПП"', 'http://avtomaster14.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "НАВИКОН"', 'https://navicontmb.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "НАСТКОМ"', 'tahografvsem.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ОБОРОНСЕРВИС"', 'https://oboronservis.clients.site/#extras', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ОП "ОСТРОВ"', 'itacho.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ПЕНЗА-ГЛОНАСС"', 'glonass58.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ПКФ "ПРОФФИТ КОНСАЛТИНГ"', 'www.proffit2000.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ПМК"', 'firstmk.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ПСК"', 'https://psk-auto.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ПУЛЬСАН"', '1tahograf.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "РДЦ"', 'рдц35.рф', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "РНИС"', 'http://rnis41.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "САНТЕЛ СЕРВИС"', 'suntel-srv.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "СИБТЕКО"', 'sibtecogroup.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "СИБТРАНСНАВИГАЦИЯ"', 'rnic42.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО ПК "СКТ"', 'glonass24.com', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "СЛОГГЕР"', 'https://www.gpskomi.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО " СМ"', 'gpsamur.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "СПЕЦТЕХКОМПЛЕКТ"', 'taho155.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТАТАСУ"', 'asusputnik.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ТАХОКАРТ', 'http://www.rctahograf.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТВКОМ"', 'https://tvcom.su/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТЕХНОЛОГИЯ - ТЮМЕНЬ"', 'http://www.tt-72.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('АО "ТНЦ"', 'tncrb.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТОРГМОНТАЖ-ПЛЮС"', 'http://www.omnicomm-magadan.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТРЭЙД ИНЖИНИРИНГ ТВЕРЬ"', 'https://tahograf69.ru/', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ФОРСАВТО"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ЦБ АУТСОРСИНГ"', 'dskazan.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ЦИФРОВОЕ ПРИМОРЬЕ"', 'digitalprimorye.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ЭСМИКОМ И К"', 'esmikom.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('Навитренд Сервис', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ВЕГА-СТОЛИЦА"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "НИЦ ГЛОНАСС"', 'www..omsk-glonass.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('АО "РНИЦ ПО РЯЗАНСКОЙ ОБЛАСТИ"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТАХОГРАФ-КАЗАНЬ"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "ТАХОСЕРВИС-БАЛТ"', '', ARRAY['интегратор', 'второстепенный конкурент']),
('ООО "АДВАНТУМ"', 'https://advantum.ru/', ARRAY['вендор']),
('ООО "АНТОР БИЗНЕС РЕШЕНИЯ"', 'www.antor.ru', ARRAY['интегратор', 'второстепенный конкурент']),
('АО "ГРУППА Т-1"', 't1-group.ru', ARRAY['интегратор', 'второстепенный конкурент']);

-- =============================================================================
-- Шаг 2: Создаем группы, которых еще нет в БД
-- =============================================================================

WITH unique_categories AS (
    SELECT DISTINCT unnest(categories) AS category_name
    FROM csv_competitors
)
INSERT INTO groups (name, color, sort_order)
SELECT uc.category_name, '#6B7280', 999
FROM unique_categories uc
WHERE NOT EXISTS (SELECT 1 FROM groups g WHERE LOWER(TRIM(g.name)) = LOWER(TRIM(uc.category_name)));

-- Обновляем sort_order для новых групп
UPDATE groups SET sort_order = (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM groups WHERE sort_order < 999)
WHERE sort_order = 999;

-- =============================================================================
-- Шаг 3: Находим конкурентов из файла, которых НЕТ в БД (для отчета)
-- =============================================================================

SELECT '=== КОНКУРЕНТЫ ИЗ ФАЙЛА, КОТОРЫХ НЕТ В БД ===' as info;

SELECT csv.name, csv.website, array_to_string(csv.categories, ', ') as categories
FROM csv_competitors csv
LEFT JOIN competitors c ON LOWER(TRIM(c.name)) = LOWER(TRIM(csv.name))
WHERE c.id IS NULL
ORDER BY csv.name;

-- =============================================================================
-- Шаг 4: Удаляем все текущие связи competitor_groups для конкурентов из файла
-- =============================================================================

DELETE FROM competitor_groups
WHERE competitor_id IN (
    SELECT c.id
    FROM competitors c
    JOIN csv_competitors csv ON LOWER(TRIM(c.name)) = LOWER(TRIM(csv.name))
);

-- =============================================================================
-- Шаг 5: Создаем новые связи competitor_groups на основе файла
-- =============================================================================

INSERT INTO competitor_groups (competitor_id, group_id)
SELECT c.id, g.id
FROM competitors c
JOIN csv_competitors csv ON LOWER(TRIM(c.name)) = LOWER(TRIM(csv.name))
CROSS JOIN LATERAL unnest(csv.categories) AS cat
JOIN groups g ON LOWER(TRIM(g.name)) = LOWER(TRIM(cat))
ON CONFLICT (competitor_id, group_id) DO NOTHING;

-- =============================================================================
-- Шаг 6: Выключаем конкурентов, которых НЕТ в файле (is_active = false)
-- =============================================================================

UPDATE competitors
SET is_active = false
WHERE id NOT IN (
    SELECT c.id
    FROM competitors c
    JOIN csv_competitors csv ON LOWER(TRIM(c.name)) = LOWER(TRIM(csv.name))
);

-- Показываем выключенных конкурентов
SELECT '=== КОНКУРЕНТЫ ВЫКЛЮЧЕНЫ ИЗ СКАНИРОВАНИЯ ===' as info;

SELECT name, url
FROM competitors
WHERE is_active = false
ORDER BY name;

-- =============================================================================
-- Шаг 7: Удаляем группы, которых нет в файле (и их связи)
-- =============================================================================

-- Сначала удаляем связи с группами, которых нет в файле
DELETE FROM competitor_groups
WHERE group_id IN (
    SELECT g.id
    FROM groups g
    WHERE NOT EXISTS (
        SELECT 1 FROM (
            SELECT DISTINCT unnest(categories) AS cat FROM csv_competitors
        ) cats WHERE LOWER(TRIM(cats.cat)) = LOWER(TRIM(g.name))
    )
);

-- Затем удаляем сами группы
DELETE FROM groups g
WHERE NOT EXISTS (
    SELECT 1 FROM (
        SELECT DISTINCT unnest(categories) AS cat FROM csv_competitors
    ) cats WHERE LOWER(TRIM(cats.cat)) = LOWER(TRIM(g.name))
);

-- =============================================================================
-- Шаг 8: Показываем итоговую статистику
-- =============================================================================

SELECT '=== ИТОГОВАЯ СТАТИСТИКА ===' as info;

SELECT 'Всего групп в БД' as metric, COUNT(*) as value FROM groups
UNION ALL
SELECT 'Всего конкурентов в БД', COUNT(*) FROM competitors
UNION ALL
SELECT 'Активных конкурентов', COUNT(*) FROM competitors WHERE is_active = true
UNION ALL
SELECT 'Выключенных конкурентов', COUNT(*) FROM competitors WHERE is_active = false
UNION ALL
SELECT 'Связей competitor_groups', COUNT(*) FROM competitor_groups;

-- Показываем группы и количество конкурентов в каждой
SELECT '=== КОНКУРЕНТЫ ПО ГРУППАМ ===' as info;

SELECT g.name as group_name, COUNT(cg.competitor_id) as competitors_count
FROM groups g
LEFT JOIN competitor_groups cg ON g.id = cg.group_id
GROUP BY g.id, g.name
ORDER BY g.sort_order;

-- Очищаем временную таблицу
DROP TABLE csv_competitors;
