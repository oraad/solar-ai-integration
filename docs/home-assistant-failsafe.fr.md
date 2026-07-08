# Sécurité intégrée de Home Assistant (chien de surveillance du rythme cardiaque)

Lorsque l'optimiseur solaire-ai s'arrête ou se bloque, Home Assistant peut détecter un
battement de cœur et active la charge du réseau au courant maximum – la même résilience
action que l'optimiseur applique lors d'un arrêt progressif ou via le kill switch.

## Conditions préalables

- solar-ai-optimizer connecté à Home Assistant (module complémentaire ou Docker) — voir[Configuration de l'assistant à domicile](home-assistant-setup.md)
- Entités de l'onduleur **écrire** mappées dans Paramètres → Onduleur (activation de la charge du réseau + courant de charge maximum du réseau)
- Batterie **Courant de charge maximum du réseau (A)** défini dans Paramètres → Batterie

## Étape 1 — Importez le package HA

Activer les packages dans`configuration.yaml`si nécessaire - voir
[Configuration de Home Assistant → Activer les packages](home-assistant-setup.md#enable-packages-in-configurationyaml).

Copier [`examples/home-assistant/packages/solar-optimizer-failsafe.yaml`](https://github.com/oraad/solar-ai-optimizer/blob/main/examples/home-assistant/packages/solar-optimizer-failsafe.yaml) dans votre Home Assistant`config/packages/`répertoire (ou fusionner dans`configuration.yaml`).

Le package définit :

| Entité | Objectif |
|--------|---------|
| `input_datetime.solar_optimizer_heartbeat`| Horodatage du battement de coeur (mis à jour par l'optimiseur) |
| `input_number.solar_optimizer_max_grid_charge_a`| Courant de charge maximum du réseau pour l'automatisation de sécurité |
| `binary_sensor.solar_optimizer_healthy`| Capteur de modèle (périmé si battement de coeur > 120 s) |

Modifiez les espaces réservés avant de recharger :

- `switch.YOUR_GRID_CHARGE_ENTITY`— identique à Paramètres → Onduleur → Activation de la charge du réseau
- `number.YOUR_MAX_GRID_CHARGE_CURRENT`— identique à Paramètres → Onduleur → Courant de charge maximum du réseau
- `input_number.solar_optimizer_max_grid_charge_a`**initial** — correspond à la charge du réseau → Courant de charge du réseau maximum (A)

Rechargez les assistants, les modèles et les automatisations après l'édition.

## Étape 2 — Configurer l'optimiseur

Dans le tableau de bord **Paramètres** → **Fail-safe** :

| Champ | Valeur |
|-------|--------|
| Battement de coeur activé | Sur |
| Entité de battement de coeur |`input_datetime.solar_optimizer_heartbeat`(par défaut) |
| Arrêt sécurisé activé | Activé (par défaut) |

Enregistrez les modifications.

Vérifiez dans **Outils de développement** → **États** que`input_datetime.solar_optimizer_heartbeat`met à jour chaque intervalle de boucle de contrôle (par défaut ~ 30 s).

Si vous avez déjà créé l'assistant manuellement avec un ID d'entité différent, définissez **Entité Heartbeat** pour qu'elle corresponde.

## Comment ça marche

```text
Package creates     →  input_datetime.solar_optimizer_heartbeat
Optimizer (alive)   →  pulses that entity each control cycle
HA template sensor  →  binary_sensor.solar_optimizer_healthy (fresh if < 120s)
HA automation       →  if unhealthy for 2 min → grid ON + max current
Optimizer shutdown  →  grid ON + max current (before process exits)
Kill switch         →  grid ON + max current + pause + restore sheds
```

## Réglage

| Paramètre | suggéré | Remarques |
|-----------|-----------|--------|
| Seuil obsolète du modèle | 90-120 ans | ~ 3 à 4 × boucle de contrôle par défaut de 30 s |
| Automation`for:`| 2 à 3 minutes | Survit aux redémarrages sans faux déclencheurs |
| `input_number.solar_optimizer_max_grid_charge_a`| Correspondre à la configuration des frais de réseau de l'optimiseur | HA n'a pas de lecture directe des paramètres de l'optimiseur |

## Limites

- Heartbeat nécessite que le processus d'optimisation s'exécute et atteigne Home Assistant.
- L'arrêt progressif sans échec ne fonctionne pas`kill -9`ou perte de puissance : comptez sur l'automatisation HA en cas de panne grave.
- L'automatisme HA écrit directement les entités de l'onduleur ; il n'appelle pas l'API de l'optimiseur (qui peut être en panne).

## API de santé

`GET /api/health`comprend :

- `heartbeat_configured`— entité de battement de cœur définie et activée
- `heartbeat_last_pulse`— dernière impulsion réussie (horodatage ISO)

Compteurs de métriques :`heartbeat_pulses_total`, `heartbeat_failures`.
