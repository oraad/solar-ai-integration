# مساعد منزلي آمن من الفشل (مراقبة نبضات القلب)

عندما يتوقف مُحسِّن الطاقة الشمسية أو يتوقف، يستطيع Home Assistant اكتشاف وجود مشكلة قديمة
نبضات القلب وتمكين شحن الشبكة بأقصى تيار - نفس المرونة
الإجراء الذي يطبقه المحسن عند إيقاف التشغيل بسلاسة أو عبر مفتاح الإيقاف.

## المتطلبات الأساسية

- محسّن الطاقة الشمسية AI متصل بـ Home Assistant (وظيفة إضافية أو Docker) - راجع[إعداد مساعد المنزل](home-assistant-setup.md)
- العاكس ** كتابة ** الكيانات المعينة في الإعدادات → العاكس (تمكين شحن الشبكة + الحد الأقصى لتيار شحن الشبكة)
- البطارية ** الحد الأقصى لتيار شحن الشبكة (A) ** تم ضبطه في الإعدادات → البطارية

## الخطوة 1 - استيراد حزمة HA

تمكين الحزم في`configuration.yaml`إذا لزم الأمر - انظر
[إعداد مساعد المنزل → تمكين الحزم](home-assistant-setup.md#enable-packages-in-configurationyaml).

ينسخ [`examples/home-assistant/packages/solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml) في مساعد منزلك`config/packages/`الدليل (أو الدمج في`configuration.yaml`).

تحدد الحزمة:

| الكيان | الغرض |
|--------|---------|
| `input_datetime.solar_optimizer_heartbeat`| الطابع الزمني لنبضات القلب (تم تحديثه بواسطة المُحسِّن) |
| `input_number.solar_optimizer_max_grid_charge_a`| الحد الأقصى لتيار شحن الشبكة للأتمتة الآمنة من الفشل |
| `binary_sensor.solar_optimizer_healthy`| مستشعر القالب (لا معنى له في حالة نبضات القلب> 120 ثانية) |

تحرير العناصر النائبة قبل إعادة التحميل:

- `switch.YOUR_GRID_CHARGE_ENTITY`- مثل الإعدادات ← العاكس ← تمكين شحن الشبكة
- `number.YOUR_MAX_GRID_CHARGE_CURRENT`- نفس الإعدادات ← العاكس ← الحد الأقصى لتيار شحن الشبكة
- `input_number.solar_optimizer_max_grid_charge_a`**الأولي** — مطابقة شحن الشبكة ← تيار شحن الشبكة الأقصى (A)

قم بإعادة تحميل المساعدين والقوالب وعمليات التشغيل الآلي بعد التحرير.

## الخطوة 2 - تكوين المحسن

في لوحة التحكم **الإعدادات** → **الفشل الآمن**:

| المجال | القيمة |
|-------|--------|
| تمكين نبضات القلب | على |
| كيان نبض القلب |`input_datetime.solar_optimizer_heartbeat`(افتراضي) |
| تم تمكين إيقاف التشغيل الآمن من الفشل | تشغيل (افتراضي) |

حفظ التغييرات.

تحقق من **أدوات المطورين** → **يذكر** ذلك`input_datetime.solar_optimizer_heartbeat`يقوم بتحديث كل فاصل زمني لحلقة التحكم (افتراضي ~ 30 ثانية).

إذا قمت بالفعل بإنشاء المساعد يدويًا باستخدام معرف كيان مختلف، فاضبط **كيان Heartbeat** للمطابقة.

## كيف يعمل

```text
Package creates     →  input_datetime.solar_optimizer_heartbeat
Optimizer (alive)   →  pulses that entity each control cycle
HA template sensor  →  binary_sensor.solar_optimizer_healthy (fresh if < 120s)
HA automation       →  if unhealthy for 2 min → grid ON + max current
Optimizer shutdown  →  grid ON + max current (before process exits)
Kill switch         →  grid ON + max current + pause + restore sheds
```

## ضبط

| المعلمة | مقترح | ملاحظات |
|-----------|-----------|--------|
| قالب عتبة قديمة | 90-120 ثانية | ~3–4× حلقة التحكم الافتراضية 30 ثانية |
| الأتمتة`for:`| 2–3 دقائق | يتم إعادة تشغيل البقاء على قيد الحياة بدون مشغلات خاطئة |
| `input_number.solar_optimizer_max_grid_charge_a`| مطابقة تكوين رسوم الشبكة للمحسن | ليس لدى HA قراءة مباشرة لإعدادات المحسن |

## القيود

- يتطلب Heartbeat تشغيل عملية المُحسّن والوصول إلى Home Assistant.
- لا يعمل إيقاف التشغيل الآمن من الفشل`kill -9`أو فقدان الطاقة - اعتمد على أتمتة HA في حالات الأعطال الشديدة.
- تقوم أتمتة HA بكتابة الكيانات العاكسة مباشرة؛ ولا يستدعي واجهة برمجة التطبيقات للمُحسِّن (والتي قد تكون معطلة).

## واجهة برمجة التطبيقات الصحية

`GET /api/health`يشمل:

- `heartbeat_configured`— تم ضبط كيان نبضات القلب وتمكينه
- `heartbeat_last_pulse`— آخر نبضة ناجحة (الطابع الزمني ISO)

عدادات القياس:`heartbeat_pulses_total`, `heartbeat_failures`.
