# ADR-006 — Workflow Engine

## Statut

Accepté

## Contexte

La plateforme RKJO AI dispose désormais des briques suivantes :

- Kernel
- EventBus RabbitMQ
- BaseAgent
- Agent Registry
- Agent Discovery
- Orchestrator
- AgentRuntime

Ces composants permettent de déclarer, localiser, sélectionner et exécuter des agents.

Il manque toutefois une couche capable de coordonner plusieurs étapes métier dans un ordre déterminé, de conserver leur état d'exécution et de gérer les erreurs de manière contrôlée.

## Décision

Un composant nommé `Workflow Engine` est introduit dans le Kernel.

Le Workflow Engine sera responsable de :

- représenter une définition de workflow ;
- ordonner plusieurs étapes ;
- conserver le contexte d'exécution ;
- suivre le statut global du workflow ;
- suivre le statut de chaque étape ;
- interrompre une exécution en cas d'échec ;
- préparer les futures stratégies de reprise ;
- fournir un historique d'exécution exploitable par le monitoring.

## Séparation des responsabilités

### Workflow Engine

Le Workflow Engine coordonne les étapes métier.

Il sait :

- quelle étape doit être exécutée ;
- dans quel ordre ;
- avec quel contexte ;
- quel est l'état courant du workflow.

Il ne choisit pas directement l'agent métier le plus pertinent.

### Orchestrator

L'Orchestrator sélectionne l'agent capable de traiter une intention ou une tâche.

Il ne conserve pas l'état complet d'un workflow métier.

### AgentRuntime

L'AgentRuntime exécute un agent et gère son cycle de vie technique.

Il ne décide ni de l'ordre des étapes ni de la logique métier globale.

## Modèle initial

Le premier incrément contiendra uniquement le modèle de domaine :

- `WorkflowStatus`
- `StepStatus`
- `WorkflowStep`
- `WorkflowDefinition`
- `WorkflowContext`
- `WorkflowExecution`

Aucune intégration RabbitMQ ne sera ajoutée dans ce premier incrément.

Aucune persistance en base de données ne sera ajoutée dans ce premier incrément.

## Statuts du workflow

Les statuts initiaux sont :

- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `CANCELLED`

## Statuts d'une étape

Les statuts initiaux sont :

- `PENDING`
- `RUNNING`
- `COMPLETED`
- `FAILED`
- `SKIPPED`

## Conséquences positives

- séparation claire entre coordination, sélection et exécution ;
- modèle testable indépendamment de RabbitMQ ;
- fondation pour les processus métier longs ;
- meilleure traçabilité ;
- future intégration simplifiée avec le monitoring et l'audit.

## Risques

- complexification du Kernel ;
- risque de chevauchement entre Workflow Engine et Orchestrator ;
- nécessité future de définir les stratégies de reprise et d'idempotence.

## Mesures de maîtrise

- maintenir une séparation stricte des responsabilités ;
- commencer par un modèle de domaine minimal ;
- couvrir chaque transition d'état par des tests unitaires ;
- différer la persistance et la messagerie aux incréments suivants.
