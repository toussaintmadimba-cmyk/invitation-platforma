# Concepts structurants du projet

Ce document ne décrit pas chaque fichier. Il rassemble les notions nécessaires pour comprendre comment les grandes parties de l'application travaillent ensemble.

## Architecture web requête-réponse

**Rencontré dans :** `platform_app/routes/`, `platform_app/templates/`.

**Pourquoi il existe ici :** le navigateur envoie une requête HTTP à une adresse. Flask choisit une route, exécute le traitement, puis renvoie une page HTML, une redirection, un fichier ou du JSON.

**À retenir :** le navigateur ne parle pas directement à la base. Les routes backend servent d'intermédiaire et appliquent validation et permissions.

**Exemple du projet :** le formulaire de `templates/client/events.html` envoie `POST /client/events`. `events_create()` dans `routes/client.py` valide les champs, crée un objet `Event`, l'enregistre et redirige vers la liste.

## Application factory et Blueprints Flask

**Rencontré dans :** `platform_app/__init__.py`, `run.py`, `wsgi.py`, `platform_app/routes/`.

**Pourquoi il existe ici :** `create_app()` construit l'application, charge sa configuration, branche la base, les sessions, CSRF et les groupes de routes. Les Blueprints répartissent les routes par responsabilité : `auth`, `client`, `admin` et `public`.

**À retenir :** `run.py` et `wsgi.py` sont des portes d'entrée ; l'application réelle est assemblée dans `create_app()`. Un Blueprint est un groupe de routes, pas une application indépendante.

**Exemple du projet :** toutes les routes du Blueprint `client` reçoivent le préfixe `/client` lors de sa création.

## Frontend rendu côté serveur avec Jinja

**Rencontré dans :** `platform_app/templates/`, `platform_app/static/`.

**Pourquoi il existe ici :** Flask prépare les données et Jinja produit le HTML envoyé au navigateur. Bootstrap fournit la présentation ; un peu de JavaScript gère le compte à rebours et les générations par lots.

**À retenir :** il n'y a pas de frontend React/Vue séparé ni d'API générale. La majorité des pages sont construites sur le serveur. Le JavaScript appelle toutefois une route JSON pour générer les invitations.

**Exemple du projet :** `invitations.html` appelle par `fetch` la route de génération, reçoit `files_generated`, `errors` et `next_offset`, puis actualise la barre de progression.

## ORM SQLAlchemy et modèle relationnel

**Rencontré dans :** `platform_app/models.py`.

**Pourquoi il existe ici :** SQLAlchemy permet au code Python de manipuler des objets tout en stockant leurs données dans des tables SQLite ou PostgreSQL.

**À retenir :** un objet Python correspond généralement à une ligne. Les clés étrangères représentent les liens métier entre tables. Les contraintes protègent aussi la base lorsque les données ne passent pas par un formulaire.

**Exemple du projet :** `Event.user_id` relie un événement à son propriétaire ; `Guest.event_id` relie un invité à l'événement ; `Invitation.guest_id` est unique, donc un invité ne peut avoir qu'une invitation ; `RSVP.invitation_id` relie une réponse à cette invitation.

## Migration Alembic

**Rencontré dans :** `migrations/versions/`, `init_db.py`, `migrate_sqlite.py`.

**Pourquoi il existe ici :** modifier `models.py` décrit la structure attendue par le code, mais ne transforme pas les bases déjà créées. Une migration applique cette évolution de manière ordonnée.

**À retenir :** le modèle Python et le schéma réel doivent rester alignés. Une migration de production agit sur les vraies données et nécessite donc sauvegarde et vérification.

**Exemple du projet :** `7d3f4b2a91c8_add_invitation_templates.py` crée la table `template`, insère `template_001`, ajoute `event.template_id`, rattache les événements existants, puis rend la colonne obligatoire.

## Authentification, session et autorisation

**Rencontré dans :** `routes/auth.py`, `routes/client.py`, `routes/admin.py`, `platform_app/__init__.py`.

**Pourquoi il existe ici :** l'authentification détermine qui est connecté. L'autorisation vérifie ensuite son rôle et la propriété des données demandées.

**À retenir :** `@login_required` ne suffit pas pour tout protéger. Le projet vérifie aussi `role` et, côté client, compare `event.user_id` à `current_user.id`.

**Exemple du projet :** `_get_client_event_or_404()` charge l'événement puis refuse l'accès si son propriétaire n'est pas l'utilisateur connecté. `admin_required` réserve la gestion des comptes au rôle `admin`.

## Protection CSRF

**Rencontré dans :** `platform_app/__init__.py` et les formulaires Jinja.

**Pourquoi il existe ici :** CSRF empêche un autre site de faire envoyer silencieusement par le navigateur une action au nom d'un utilisateur connecté.

**À retenir :** les opérations qui modifient des données utilisent POST et transmettent un jeton CSRF. Le serveur rejette les requêtes sans jeton valide.

**Exemple du projet :** la réponse RSVP est enregistrée uniquement par `POST /i/<code>/rsvp`. Le lien PDF ouvre d'abord une confirmation en GET, puis le formulaire protégé effectue le changement.

## Transaction, commit et rollback

**Rencontré dans :** les routes et `services/invitation_generator.py`.

**Pourquoi il existe ici :** une transaction regroupe des changements de base. `commit` les confirme ; `rollback` abandonne ceux qui ont échoué.

**À retenir :** la génération combine base de données et appel réseau, donc elle doit éviter qu'un échec d'un invité annule les succès précédents ou laisse des fichiers incohérents.

**Exemple du projet :** le générateur réserve d'abord un code stable, fabrique PDF et QR, les envoie, puis met à jour l'invitation. En cas d'erreur, il annule la transaction courante et tente de supprimer la nouvelle paire envoyée.

## Couche de services

**Rencontré dans :** `platform_app/services/`.

**Pourquoi il existe ici :** les opérations techniques complexes sont séparées des routes HTTP : rendu d'une invitation, stockage distant et récupération de mot de passe.

**À retenir :** une route orchestre la demande utilisateur ; un service porte une opération réutilisable ou une intégration technique.

**Exemple du projet :** `routes/client.py` déclenche `generate_all_invitations_for_event()`, qui utilise ensuite `TemplateRenderer` et `upload_invitation_files()`.

## Stockage réparti

**Rencontré dans :** `models.py`, `storage/templates/`, `services/cloud_storage.py`.

**Pourquoi il existe ici :** toutes les informations ne sont pas du même type. Les données métier vont en base ; les ressources du modèle sont dans le dépôt ; les fichiers générés sont envoyés vers Cloudinary.

**À retenir :** la base contient les URL des PDF et QR, pas normalement leur contenu. Sauvegarder PostgreSQL ne sauvegarde pas automatiquement Cloudinary, et inversement.

**Exemple du projet :** `Invitation.pdf_path` et `qr_path` reçoivent les URL HTTPS renvoyées par Cloudinary. `storage/templates/template_001/template.json` décrit comment composer le PDF à partir des quatre images de fond.

## Configuration et variables d'environnement

**Rencontré dans :** `platform_app/config.py`, `.env.example`, `render.yaml`.

**Pourquoi il existe ici :** les adresses de services, mots de passe et clés ne doivent pas être codés dans le dépôt. L'environnement local et Render fournissent leurs propres valeurs.

**À retenir :** une variable d'environnement modifie le comportement du même code selon l'endroit où il tourne. `.env.example` documente les noms, mais l'application ne charge pas automatiquement un fichier `.env`.

**Exemple du projet :** sans `DATABASE_URL`, le développement utilise `instance/app.db`. En production, la validation exige une base explicite, une `SECRET_KEY` privée et une `BASE_PUBLIC_URL` HTTPS.

## Tests automatisés et simulations

**Rencontré dans :** `tests/`.

**Pourquoi il existe ici :** les tests vérifient les comportements importants et empêchent leur régression. Les services externes sont simulés pour rendre les tests locaux rapides et reproductibles.

**À retenir :** un test prouve seulement le scénario qu'il exécute. Un mock de Cloudinary prouve la réaction du code aux réponses simulées, pas que les vrais identifiants ou le réseau fonctionnent.

**Exemple du projet :** les tests couvrent récupération de mot de passe, permissions, RSVP, quotas de groupes, concurrence de génération, sauvegardes et migration des templates. `countdown.test.js` teste séparément le calcul JavaScript.

## Déploiement

**Rencontré dans :** `render.yaml`, `wsgi.py`, `requirements.txt`.

**Pourquoi il existe ici :** Render installe les dépendances, applique les migrations, puis lance l'application avec Gunicorn.

**À retenir :** Git conserve le code ; Render exécute une version déployée de ce code ; PostgreSQL conserve les données de production. Ce sont trois responsabilités différentes.

**Exemple du projet :** la commande de démarrage déclarée est `flask --app wsgi:app db upgrade && gunicorn wsgi:app --timeout 180 --workers 3`.

## Principaux flux de données

### Création d'un événement

Navigateur → formulaire Jinja → `POST /client/events` → validation et contrôle du client → objet `Event` → transaction SQLAlchemy → SQLite/PostgreSQL → redirection → nouvelle page HTML.

### Génération d'une invitation

Bouton du navigateur → requêtes `fetch` par lots → route client protégée → invités en base → `TemplateRenderer` + ressources `storage/templates` → PDF et QR temporaires → Cloudinary → URL enregistrées dans `Invitation` → réponse JSON → progression affichée.

### Réponse RSVP

QR ou lien du PDF → code public aléatoire → recherche de `Invitation` → page publique → formulaire POST avec CSRF → création ou modification de `RSVP` → page de remerciement → statistiques visibles par le propriétaire.

### Mot de passe oublié

Adresse saisie → recherche discrète d'un compte actif → jeton signé avec durée limitée → email SMTP → lien public → validation du jeton et du mot de passe → remplacement du hash → ancien lien invalidé.

## Priorité pédagogique

### Indispensables maintenant

- requête, route et réponse HTTP ;
- modèles `User`, `Event`, `Guest`, `Invitation`, `RSVP` et leurs relations ;
- différence frontend/backend/base ;
- authentification, rôle et propriété des données ;
- migration et différence local/production.

### Importants prochainement

- transactions et gestion des erreurs ;
- services et intégrations Cloudinary/SMTP ;
- variables d'environnement et secrets ;
- tests, mocks et limites de ce qu'un test prouve ;
- cycle GitHub → Render → PostgreSQL.

### Avancés

- concurrence lors de la génération ;
- idempotence et reprise après erreur ;
- contraintes SQL et compatibilité SQLite/PostgreSQL ;
- stratégie de sauvegarde/restauration ;
- sécurité et durée de vie des jetons signés.

### Non prioritaires

- détails de dessin ReportLab en millimètres ;
- réglages internes de Gunicorn ;
- syntaxe détaillée d'Alembic ;
- fonctionnement interne de QR Code ou Pillow ;
- personnalisation fine de Bootstrap et des polices.
