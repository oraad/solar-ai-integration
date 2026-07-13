# مساعد منزلي آمن من الفشل (مراقبة نبضات القلب)

**موصى به:** ثبّت [تكامل HACS المخصص](home-assistant-integration.md)
(Home Assistant **2026.7+**). يستعلم عن Solar عبر `GET /api/health` (`heartbeat_last_pulse`)
ويشغّل المراقبة داخل HA — بلا حزمة YAML وبلا كيان مساعد نبضات قلب من Solar.

يحدّث Solar قيمة `heartbeat_last_pulse` داخل العملية في كل دورة تحكم. الإعدادات → السلامة
تضبط فقط **إيقاف التشغيل** لشحن الشبكة عند الحد الأقصى (خروج العملية بسلاسة)، وليس نبضة HA
من نوع `input_datetime`.

عندما يتوقف Solar أو يتعلّق، يمكن لـ Home Assistant اكتشاف نبضة API قديمة وتمكين
شحن الشبكة بأقصى تيار — نفس إجراء المرونة الذي يطبّقه Solar عند الإيقاف السلس أو عبر مفتاح الإيقاف.

## المتطلبات الأساسية

- solar-ai-optimizer يمكن الوصول إليه من Home Assistant — راجع [إعداد Home Assistant](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)
- تكامل HACS مقترن (أو اكتشاف المشرف على إضافة HAOS)
- لـ fail-safe مع قفل: مفتاح **تمكين شحن الشبكة** + رقم **التيار الأقصى** في خيارات التكامل
- أمبير البطارية / شحن الشبكة الأقصى مضبوط في Solar (يُستخدم عند قفل المراقبة)

## ضبط مراقبة HACS

افتح **تهيئة** على تكامل Solar AI Optimizer:

| الخيار | الغرض |
|--------|---------|
| مفتاح تمكين شحن الشبكة | يُشغَّل عندما تصبح نبضة القلب قديمة بعد debounce |
| تيار شحن الشبكة الأقصى | كيان `number` يُضبط على أمبير شحن الشبكة الأقصى في Solar |
| ثواني التقادم | أقصى عمر لـ `heartbeat_last_pulse` قبل unhealthy (الافتراضي 120) |
| ثواني debounce | مدة بقاء unhealthy قبل القفل (الافتراضي 120) |

اضبط **كياني** fail-safe معاً أو **لا شيء**. راجع [تكامل Home Assistant](home-assistant-integration.md).

تحقق من أن Solar يعمل دورياً: يجب أن يُظهر `GET /api/health` قيمة حديثة لـ `heartbeat_last_pulse`،
وأن يبقى مستشعر التكامل الثنائي **Healthy** قيد التشغيل.

## كيف يعمل (HACS)

```text
دورة تحكم Solar  →  تقدّم heartbeat_last_pulse (داخل العملية)
HACS يستعلم /api/health →  مستشعر Healthy الثنائي / مراقبة fail-safe
Unhealthy + debounce →  switch.turn_on + number.set_value (أمبير أقصى)
إيقاف Solar السلس  →  الشبكة ON + تيار أقصى (الإعدادات → السلامة إيقاف fail-safe)
مفتاح الإيقاف          →  الشبكة ON + تيار أقصى + إيقاف مؤقت + استعادة فصول الأحمال
```

## حزمة YAML القديمة (لا تستخدم مع HACS)

قد تحتفظ التثبيتات الأقدم بـ
[`solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml).
كانت تلك الحزمة تراقب `input_datetime.solar_optimizer_heartbeat`، والذي **لم تعد إصدارات Solar
الحالية تكتبه**. عطّل الحزمة عند استخدام تكامل HACS لتجنب إجراءات شحن شبكة مزدوجة. لا تستوردها التثبيتات الجديدة.

## القيود

- تتطلب نبضة API تشغيل عملية Solar والرد على `/api/health`.
- لا يعمل إيقاف التشغيل الآمن السلس مع `kill -9` أو فقدان الطاقة — اعتمد على مراقبة HACS للأعطال القاسية.
- تكتب مراقبة HACS كيانات العاكس مباشرة؛ ولا تستدعي واجهة Solar لتلك الكتابات (قد يكون Solar متوقفاً).

## واجهة الصحة

`GET /api/health` يتضمن:

- `heartbeat_configured` — دائماً `true` في الإصدارات الحالية (الحيوية داخل العملية)
- `heartbeat_last_pulse` — آخر نبضة لدورة التحكم (طابع زمني ISO محلي للموقع)

عدادات المقاييس: `heartbeat_pulses_total`, `heartbeat_failures`.
