# Récupération de mot de passe et compte à rebours

## Configuration des emails

Définir les variables dans l'environnement du processus Python ou dans les variables du service Render. Le projet ne charge pas automatiquement un fichier `.env` ; `.env.example` documente les valeurs attendues.

- `SECRET_KEY` : une clé privée stable propre à la production.
- `BASE_PUBLIC_URL` : adresse HTTPS publique de l'application, sans chemin supplémentaire. Les liens envoyés utilisent cette adresse, jamais l'en-tête Host de la requête.
- `MAIL_HOST`, `MAIL_PORT`, `MAIL_FROM` : serveur SMTP, port et adresse d'expédition autorisée.
- `MAIL_USERNAME`, `MAIL_PASSWORD` : identifiants SMTP fournis par le service email.
- Port 587 : `MAIL_USE_TLS=true`, `MAIL_USE_SSL=false`.
- Port 465 : `MAIL_USE_SSL=true`, `MAIL_USE_TLS=false`.

Depuis Connexion, ouvrir « Mot de passe oublié ? ». Le lien reçu expire après 30 minutes. Un changement de mot de passe invalide tous les liens de récupération précédents. Le formulaire exige deux saisies identiques de 8 à 256 caractères. Un compte suspendu ne peut pas être réactivé par ce parcours.

L'écran retourne le même message pour une adresse inconnue, suspendue ou connue. En cas d'échec SMTP, consulter les journaux du serveur et vérifier la configuration ; aucun jeton ni mot de passe SMTP n'est écrit par le gestionnaire d'erreur. L'envoi réel doit être vérifié avec une boîte de test après configuration SMTP. Les tests locaux simulent le serveur email.

## Compte à rebours

Le tableau de bord affiche un compte à rebours pour chaque événement actif. Il apparaît également sur la page de modification de l'événement, et se met à jour chaque seconde. Après enregistrement d'une nouvelle date, il utilise la nouvelle échéance. Une échéance atteinte affiche un message et ne produit jamais de valeurs négatives. Les événements inactifs n'affichent pas de compte à rebours.

Les dates existantes sont enregistrées sans fuseau horaire. Le calcul les interprète donc dans le fuseau du navigateur, explicitement indiqué à l'écran. Un organisateur dans un autre fuseau que celui du lieu doit en tenir compte ; la gestion d'un fuseau propre à chaque événement reste une évolution distincte. Le compte à rebours dépend également de l'horloge du téléphone ou de l'ordinateur. Il n'apparaît pas sur les invitations publiques.

Aucune migration des tables existantes n'est nécessaire.

Cette absence de migration concerne uniquement le mot de passe et le compte à rebours. Le lot de stabilisation ci-dessous exige une migration des bases existantes.

## Vérification locale

Depuis la racine du projet, sous Windows :

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
node tests/countdown.test.js
```

Les tests Python utilisent uniquement une base SQLite temporaire en mémoire et un serveur SMTP simulé. Ils couvrent la récupération, les liens invalides/expirés/réutilisés, la protection CSRF, les comptes suspendus, la connexion, l'isolation des clients, la création/modification des événements et une réponse publique RSVP. Les tests JavaScript couvrent le calcul du compte à rebours, les échéances atteintes et les dates invalides.

## Lot 1 — Stabilisation du 8 septembre 2026

### Génération et RSVP

- Chaque invitation réserve un code stable, puis enregistre sa paire PDF/QR dans une transaction indépendante. Une erreur ne retire plus les succès précédents du lot.
- Une invitation dont la génération échoue peut exister sans fichiers : relancer la génération des fichiers manquants. Elle conserve le même code.
- Deux générations concurrentes ne peuvent plus créer deux invitations pour le même invité. Une mise à jour concurrente des fichiers est refusée et peut être retentée.
- Les fichiers Cloudinary utilisent une révision aléatoire, sans écrasement de la précédente. Un échec du second upload nettoie uniquement la nouvelle révision. Les anciennes révisions réussies sont conservées ; leur purge future devra tenir compte des liens déjà partagés. Un arrêt brutal du processus peut laisser des fichiers orphelins à rapprocher.
- Le lot est limité à 50 invités côté serveur. Une fin de lot avec erreurs n’apparaît plus en vert.
- Les anciens liens PDF `/i/<code>/rsvp?status=yes|no` ouvrent un écran de confirmation. Seul le POST avec jeton CSRF enregistre la réponse. Le choix « plus tard » revient à l’invitation.
- Une invitation d’un événement inactif ou d’un propriétaire suspendu retourne 404 sur tous les parcours publics. Cela ne révoque pas les fichiers déjà téléchargés ni les anciennes URL Cloudinary.

### Groupes et compteurs

Règles côté formulaire, serveur et base : personne seule = 1 ; couple = 2 ; famille = 2 à 100. Sans taille saisie, les valeurs par défaut sont 1, 2 et 3. Une valeur explicite incompatible est refusée.

Le tableau de bord affiche les personnes invitées et les groupes, sans les appeler « confirmés ». Les compteurs RSVP comptent des invitations acceptées/refusées, pas des personnes présentes.

### Sauvegarde et migration

Avant toute migration, arrêter les opérations métier et sauvegarder. Le script ci-dessous sauvegarde les bases SQLite locales et le répertoire `storage` du dépôt ; il ne sauvegarde **ni PostgreSQL sur Render ni les fichiers distants Cloudinary**. Les sauvegardes sont ignorées par Git et doivent aussi être copiées sur un support séparé.

```powershell
.\.venv\Scripts\python.exe maintenance.py backup
.\.venv\Scripts\python.exe maintenance.py verify-backup backups/20260908T015040504252Z
.\.venv\Scripts\python.exe maintenance.py migrate
.\.venv\Scripts\python.exe maintenance.py migrate --apply
```

La commande `backup` affiche son propre dossier horodaté : utiliser ce chemin lors des vérifications suivantes. Elle vérifie les empreintes et restaure chaque copie SQLite dans un dossier temporaire pour en contrôler l’intégrité. Ne pas écraser la base active pour tester une restauration.

`migrate` sans option inventorie seulement les groupes invalides et doublons. `--apply` refuse les anomalies au lieu de supprimer des invitations ou de deviner une taille. Après un inventaire sans anomalie, il ajoute une unicité sur `invitation.guest_id`, la validation des groupes et la version `001_stabilisation`. Sous SQLite, des triggers conservent les colonnes historiques ; sous PostgreSQL, une contrainte CHECK est utilisée. Réexécuter la migration est sans effet destructif.

La migration locale a été appliquée après la sauvegarde `backups/20260908T015040504252Z`. Comparaison avant/après : toutes les lignes des cinq tables métier sont inchangées.

Sur Render : sauvegarder la base avec le mécanisme de l’hébergement ou les outils PostgreSQL, puis lancer `python maintenance.py migrate` et `python maintenance.py migrate --apply` dans un environnement qui dispose de `DATABASE_URL`. Valider d’abord sur une copie de test. Le chemin PostgreSQL du script n’a pas été exécuté ici. L’application refuse désormais un ancien schéma dépourvu des protections requises.

Pour une restauration réelle locale : arrêter l’application, conserver une copie de l’état courant, vérifier la sauvegarde puis restaurer la base et les ressources locales correspondantes. Restaurer dans un nouveau chemin et tester avec `DATABASE_URL`/`STORAGE_DIR` pointant vers cette copie avant de basculer. Une sauvegarde antérieure à ce lot nécessite de réappliquer la migration avant le démarrage du nouveau code.

### Emails et Cloudinary sur Render

Les identifiants sont configurés sur Render d’après l’organisateur ; ils ne sont pas accessibles dans le processus local. Aucun secret n’a été copié dans le dépôt et aucun email réel n’a été envoyé pendant cette intervention.

Le projet lit les variables du processus, pas automatiquement `.env`. Redémarrer le service après modification des variables. `render.yaml` documente les paramètres à fournir sans embarquer leurs valeurs.

```bash
python check_services.py
python check_services.py --send-test adresse-de-test@example.com
```

La première commande affiche seulement présence/absence des paramètres et cohérence SMTP/production ; elle ne contacte pas les fournisseurs. La seconde envoie explicitement un email sans jeton de récupération à l’adresse indiquée. L’acceptation SMTP n’est pas une preuve de réception : vérifier la boîte et les indésirables, puis tester une vraie récupération sur un compte de test (expiration et réutilisation comprises).

Utiliser exactement un transport chiffré : STARTTLS (`MAIL_USE_TLS=true`, `MAIL_USE_SSL=false`) ou SSL direct (valeurs inversées). Identifiant et mot de passe vont ensemble. En production, une clé privée, une base explicitement configurée et une origine HTTPS publique sont obligatoires.

Pour Cloudinary : vérifier les trois variables, générer deux invitations fictives dans l’environnement de test, puis vérifier leur téléchargement. Le test local utilise le vrai moteur PDF/QR et simule l’envoi distant ; il ne valide ni les droits Cloudinary ni la connectivité Render.

### Vérifications de ce lot

La suite de stabilisation teste les défauts reproduits, les contraintes en base, les générations simultanées sur SQLite temporaire, l’échec d’une régénération, le nettoyage du nouvel upload après erreur, les transports SMTP simulés, ainsi que sauvegarde/restauration et détection d’altération. Les données de test sont en mémoire ou dans des dossiers temporaires.

La réception email réelle, les uploads réels, la migration PostgreSQL et le rendu mobile restent à vérifier dans l’environnement cible.
