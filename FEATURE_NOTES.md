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

## Vérification locale

Depuis la racine du projet, sous Windows :

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
node tests/countdown.test.js
```

Les tests Python utilisent uniquement une base SQLite temporaire en mémoire et un serveur SMTP simulé. Ils couvrent la récupération, les liens invalides/expirés/réutilisés, la protection CSRF, les comptes suspendus, la connexion, l'isolation des clients, la création/modification des événements et une réponse publique RSVP. Les tests JavaScript couvrent le calcul du compte à rebours, les échéances atteintes et les dates invalides.
