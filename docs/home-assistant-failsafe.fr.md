# Sécurité intégrée Home Assistant (chien de garde heartbeat)

**Recommandé :** installez l'[intégration HACS personnalisée](home-assistant-integration.md)
(Home Assistant **2026.7+**). Elle interroge Solar `GET /api/health` (`heartbeat_last_pulse`)
et exécute le chien de garde dans HA — sans package YAML ni entité helper heartbeat côté Solar.

Solar avance `heartbeat_last_pulse` en processus à chaque cycle de contrôle. Paramètres → Sécurité
ne configure que l'**arrêt** charge réseau au maximum (sortie gracieuse du processus), pas une
impulsion HA `input_datetime`.

Lorsque Solar s'arrête ou se bloque, Home Assistant peut détecter une impulsion API périmée et
activer la charge réseau au courant maximum — la même action de résilience que Solar applique
lors d'un arrêt gracieux ou via le kill switch.

## Conditions préalables

- solar-ai-optimizer joignable depuis Home Assistant — voir [Configuration Home Assistant](https://oraad.github.io/solar-ai-optimizer/home-assistant-setup/)
- Intégration HACS appairée (ou découverte Supervisor sur le module complémentaire HAOS)
- Pour un fail-safe à verrouillage : interrupteur **activation charge réseau** + nombre **courant max** dans les options de l'intégration
- Courant max batterie / charge réseau configuré dans Solar (utilisé quand le chien de garde se verrouille)

## Configurer le chien de garde HACS

Ouvrez **Configurer** sur l'intégration Solar AI Optimizer :

| Option | Objectif |
|--------|---------|
| Interrupteur activation charge réseau | Allumé lorsque le heartbeat est périmé au-delà du debounce |
| Courant max de charge réseau | Entité `number` réglée sur les ampères max de charge réseau de Solar |
| Secondes de péremption | Âge max de `heartbeat_last_pulse` avant unhealthy (défaut 120) |
| Secondes de debounce | Durée pendant laquelle unhealthy doit persister avant verrouillage (défaut 120) |

Définissez **les deux** entités fail-safe ou **aucune**. Voir [Intégration Home Assistant](home-assistant-integration.md).

Vérifiez que Solar cycle : `GET /api/health` doit montrer un `heartbeat_last_pulse` récent,
et le capteur binaire **Healthy** de l'intégration doit rester allumé.

## Fonctionnement (HACS)

```text
Cycle de contrôle Solar  →  avance heartbeat_last_pulse (en processus)
HACS interroge /api/health →  capteur binaire Healthy / chien de garde fail-safe
Unhealthy + debounce →  switch.turn_on + number.set_value (ampères max)
Arrêt gracieux Solar  →  réseau ON + courant max (Paramètres → Sécurité arrêt fail-safe)
Kill switch          →  réseau ON + courant max + pause + restauration des délestages
```

## Package YAML hérité (ne pas utiliser avec HACS)

Les anciennes installations peuvent encore avoir
[`solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml).
Ce package surveillait `input_datetime.solar_optimizer_heartbeat`, que **les builds Solar
actuels n'écrivent plus**. Désactivez le package avec l'intégration HACS pour éviter
des actions de charge réseau en double. Les nouvelles installations ne doivent pas l'importer.

## Limites

- Le heartbeat API exige que le processus Solar tourne et réponde à `/api/health`.
- L'arrêt gracieux fail-safe ne s'exécute pas sur `kill -9` ni perte de courant — comptez sur le chien de garde HACS pour les crashes durs.
- Le chien de garde HACS écrit directement les entités onduleur ; il n'appelle pas l'API Solar pour ces écritures (Solar peut être hors ligne).

## API de santé

`GET /api/health` inclut :

- `heartbeat_configured` — toujours `true` sur les builds actuels (la vivacité est en processus)
- `heartbeat_last_pulse` — dernière impulsion de cycle de contrôle (horodatage ISO local au site)

Compteurs de métriques : `heartbeat_pulses_total`, `heartbeat_failures`.
