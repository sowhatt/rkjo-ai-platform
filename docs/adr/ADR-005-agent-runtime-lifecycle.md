# ADR-005 — Le Runtime contrôle le cycle de vie des agents

## Statut

Accepté.

## Contexte

Dans RKJO AI Platform, un agent doit principalement contenir sa logique métier.

Il ne doit pas être responsable directement :

- du démarrage de son processus ;
- de la connexion à RabbitMQ ;
- de la consommation de sa file ;
- de la supervision ;
- du changement de statut dans le registre ;
- de la mesure de ses performances.

Ces responsabilités appartiennent à une couche d'exécution dédiée.

## Décision

Nous introduisons un composant `AgentRuntime`.

Le partage des responsabilités devient :

- `BaseAgent` : logique métier et traitement d'un `AgentMessage` ;
- `AgentRuntime` : cycle de vie et exécution ;
- `EventBus` : transport des messages ;
- `RegistryService` : état public des agents ;
- `AgentOrchestrator` : choix et routage des missions.

## Conséquences positives

- agents plus simples ;
- meilleure testabilité ;
- isolation de RabbitMQ ;
- supervision centralisée ;
- possibilité d'ajouter Kafka ou un bus mémoire ;
- redémarrage et arrêt contrôlés ;
- métriques homogènes.

## Conséquences négatives

- ajout d'une couche supplémentaire ;
- migration progressive des méthodes `start()` et `stop()` actuellement présentes dans `BaseAgent`.

## Stratégie de migration

Dans une première étape, `AgentRuntime` utilisera la méthode interne `_handle_message()` de `BaseAgent`.

Dans une étape ultérieure, les responsabilités de consommation et de cycle de vie seront retirées de `BaseAgent`.
