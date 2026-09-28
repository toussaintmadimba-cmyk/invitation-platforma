# Progression

## Point de départ

État initial établi le 27 septembre 2026 après lecture du dépôt.

Le projet est déjà avancé, mais son développement antérieur avec l'aide de l'IA ne permet pas de déduire quels concepts sont réellement compris. La présence d'un concept dans le code signifie seulement qu'il a été rencontré.

Objectif d'apprentissage : devenir capable d'expliquer l'architecture, de suivre une donnée, d'identifier la couche responsable d'un problème et de contrôler une modification proposée par l'IA.

## Concepts compris

Aucun concept n'est encore considéré comme validé. Ils seront déplacés ici uniquement après une explication personnelle, une réponse à une question de raisonnement ou une utilisation correcte pendant une tâche réelle.

## En apprentissage

- **Environnement local et production** — distinction récemment abordée, compréhension à vérifier.
- **Migration de base de données** — rôle général expliqué, mais lien exact entre `models.py`, Alembic et la base à consolider.
- **Git : ajout, commit et push** — commandes rencontrées ; portée exacte de chaque étape à vérifier.
- **Base de données relationnelle** — tables, lignes, identifiants et relations à relier au modèle métier du projet.

## Nouveaux concepts

Ces concepts sont structurants dans le dépôt et restent à apprendre ou à évaluer :

- cycle requête HTTP → route Flask → traitement → réponse HTML/JSON ;
- application factory Flask et Blueprints ;
- rendu serveur avec Jinja ;
- ORM SQLAlchemy, modèles et relations ;
- clés étrangères, contraintes et unicité ;
- session utilisateur, authentification et autorisation ;
- protection CSRF ;
- transaction, commit et rollback ;
- séparation routes/services ;
- stockage partagé entre base de données, fichiers de templates et Cloudinary ;
- variables d'environnement et secrets ;
- tests automatisés, simulations (`mock`) et tests d'intégration ;
- déploiement Render avec Gunicorn et PostgreSQL.

## À revoir

- Pourquoi modifier un modèle Python ne modifie pas automatiquement une base existante.
- Sur quelle base agit une commande selon qu'elle est lancée localement ou sur Render.
- Différence entre le dépôt Git, l'application locale et l'application déployée.
- Différence entre authentification (qui est connecté ?) et autorisation (que peut-il faire ?).
- Différence entre les données métier en base et les fichiers PDF, QR ou images.

## Parcours pédagogique proposé

1. Suivre la création d'un événement du formulaire jusqu'à la base.
2. Lire les modèles `User`, `Event`, `Guest`, `Invitation` et `RSVP` comme une carte métier.
3. Suivre une génération d'invitation jusqu'à Cloudinary et au lien public.
4. Comparer authentification, rôles et contrôle de propriété d'un événement.
5. Comprendre une migration Alembic à partir de l'ajout de `template_id`.
6. Lire un test existant et expliquer ce qu'il prouve réellement.
7. Reconstituer le passage local → GitHub → Render → PostgreSQL.

## Prochain checkpoint

La compréhension initiale sera évaluée avec cinq questions portant sur : architecture, flux d'un événement, relation entre tables, contrôle d'accès et migration. Les réponses serviront à déplacer les concepts entre les sections ; une explication reçue ne suffira pas à elle seule pour marquer un concept comme compris.
