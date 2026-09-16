# État du projet et plan d’évolution

Audit local du 8 septembre 2026 — référence Git : `bbf0549`, branche `codex-dev`.

## Conclusion

Le projet est un MVP fonctionnel de préparation d’invitations, avec comptes clients, événements, invités, PDF, QR et réponses RSVP. Il n’est pas encore une application de contrôle des entrées, ni un SaaS commercial prêt à exploiter sans supervision.

La priorité est de fiabiliser les parcours existants, puis de livrer un accueil simple capable de gérer les couples arrivant séparément. Un seul modèle d’invitation fiable suffit pour le premier événement pilote ; le catalogue complet peut suivre.

## Périmètre et preuves

- Lecture des modèles, routes, services, templates, configuration, scripts et tests du dépôt.
- Exécution réussie de ` .\.venv\Scripts\python.exe -m unittest discover -s tests -v` : 9 tests.
- Exécution réussie de `node tests/countdown.test.js` : 6 assertions.
- Trois essais complémentaires sur SQLite en mémoire, avec génération et Cloudinary simulés : résultats ci-dessous.
- Aucun accès aux données métier de la base locale, aucune migration exécutée, aucun email envoyé, aucun appel Cloudinary effectué.
- Pas de validation visuelle mobile, de test caméra, de test de charge ou de contrôle de la production. La présence d’un fichier Render ne prouve pas que le déploiement fonctionne.
- Aucun contrôle des vulnérabilités des dépendances effectué. Les avertissements de dépréciation Python/SQLAlchemy observés ne font pas échouer la suite.

Au début de l’audit, l’arbre Git est propre. Les fonctionnalités récentes sont désormais commitées. La branche et sa référence distante locale sont alignées ; aucun `fetch` n’a été effectué, donc cela ne certifie pas l’état actuel de GitHub.

## Fonctionnalités réellement présentes

| Domaine | État constaté | Limite principale |
|---|---|---|
| Comptes | Inscription, connexion, déconnexion, mots de passe hachés | Validation d’inscription sommaire, pas de limitation des tentatives trouvée |
| Administration | Liste des clients et suspension/réactivation | Pas de gestion du personnel d’accueil ni de demandes de personnalisation |
| Isolation clients | Contrôles du propriétaire sur événements et téléchargements | Un test d’accès croisé existe ; couverture à étendre à toutes les actions |
| Événements | Création, modification, activation, compte à rebours | Date sans fuseau, politique de désactivation publique absente |
| Invités | Ajout et suppression, civilité, groupe, table, coordonnées | Pas de route de modification trouvée ; quota insuffisamment validé |
| Invitations | Génération par lots, PDF/QR, téléchargement via URL Cloudinary | Dépendance obligatoire à Cloudinary et problème de transaction de lot |
| Modèles | Moteur JSON et un modèle A5 de quatre pages | `template_001` imposé dans le générateur ; aucun catalogue/choix par événement |
| RSVP | Réponse oui/non, message et statistiques | Réponse au niveau de l’invitation, sans détail nominatif ni quantité confirmée |
| Mot de passe oublié | Jeton signé, expiration 30 minutes, invalidation après changement | SMTP simulé dans les tests ; réception réelle non vérifiée ici |
| Accueil | QR contenant une URL publique avec code aléatoire | Aucun scanner, admission, journal de passage ou affectation d’agent |
| SaaS commercial | Socle de comptes séparés | Pas d’offres, abonnements, quotas commerciaux ou facturation trouvés |

Le champ `party_size` représente déjà les places d’un groupe, mais aucun membre individuel ni passage n’est modélisé. Le script SQLite mentionne `partner_name` ; ce champ n’est pas exploité dans les modèles et routes actuels.

## Constats à traiter

### P0 — Avant un événement pilote

**1. Une erreur de génération peut annuler les réussites précédentes du lot.**

Source : `platform_app/services/invitation_generator.py:110`, puis compteur ligne 119 et commits lignes 122/124.

Reproduction isolée : première génération simulée réussie, seconde en erreur. Résultat renvoyé : `files_generated=1`, `errors=1`. Invitations réellement conservées : **0**. Le rollback annule les changements non commités précédents, sans corriger le compteur ; des fichiers distants peuvent alors exister sans leur invitation en base.

Action : isoler la transaction de chaque invitation, compter les succès persistés et prévoir une reprise cohérente après erreur. Ajouter une unicité en base sur l’invité pour empêcher deux invitations lors de générations concurrentes : `uselist=False` ne fournit pas cette contrainte. Tester également la régénération avec fichiers existants et l’échec du second upload.

**2. Un simple GET modifie une réponse RSVP.**

Source : `platform_app/routes/public.py:41` et liens du moteur PDF.

Reproduction avec CSRF activé : `GET /i/audit-code/rsvp?status=yes` enregistre `yes`. Un préchargement ou un outil d’analyse de liens pourrait donc répondre à la place de l’invité.

Action : conserver les anciennes URL, mais leur faire afficher une confirmation ; seul un POST protégé doit enregistrer la réponse. Critère : ouvrir un lien ne modifie jamais la base.

**3. Les quotas de groupe acceptent des valeurs impossibles.**

Source : `platform_app/routes/client.py:264` à 274.

Reproduction : une famille envoyée avec `party_size=-3` est enregistrée avec **−3**. Le tableau de bord compte par ailleurs les lignes Guest, pas la somme des personnes (`client.py:74`).

Action : règles explicites pour personne seule/couple/famille, bornes côté serveur et contrainte en base. Afficher séparément invitations/groupes et personnes. Corriger les données existantes invalides par une migration contrôlée, après inventaire.

**4. Des données et artefacts d’invitation sont suivis dans Git.**

`git ls-files` confirme trois bases SQLite (`instance/app.db` et deux anciennes bases) ainsi que des QR d’événements. Leur contenu n’a pas été inspecté.

Action : sauvegarder hors Git, distinguer ressources de modèles et fichiers générés, puis arrêter le suivi des données. Examiner l’exposition passée et les accès au dépôt ; ignorer un fichier ne le supprime pas de l’historique. Une éventuelle réécriture d’historique doit faire l’objet d’une opération dédiée et coordonnée.

**5. La configuration de production n’est pas démontrée par le dépôt.**

`render.yaml` configure Gunicorn et une clé générée, mais ne déclare ni `DATABASE_URL`, ni stockage persistant, ni SMTP, ni Cloudinary. Ces paramètres peuvent exister dans la console d’hébergement : non vérifié. Sans `DATABASE_URL`, le code utilise SQLite ; sans les variables Cloudinary, la génération échoue. Les fichiers locaux de génération sont nettoyés même après un échec.

Action : inventorier les paramètres réellement déployés sans exposer leurs valeurs, vérifier la persistance, configurer les emails et tester sauvegarde/restauration. Faire refuser la clé de développement en production. Un fichier `.env` n’est pas chargé automatiquement par le projet.

### P1 — Avant ouverture à plusieurs clients

- **Accès public après désactivation :** la récupération d’invitation ne vérifie ni l’activité de l’événement ni celle de son propriétaire. La reproduction RSVP ci-dessus réussit sur un événement inactif. Définir la politique attendue et l’appliquer aux pages et actions publiques.
- **Authentification :** uniformiser les règles de mot de passe entre inscription et récupération, limiter les tentatives de connexion/récupération, examiner la révocation des sessions existantes après changement de mot de passe. Le code actuel déconnecte le navigateur de récupération, sans mécanisme global de révocation trouvé.
- **Fichiers distants :** téléchargements redirigés vers des URL Cloudinary ; les identifiants de fichiers sont construits à partir des IDs événement/invité. Vérifier les accès directs et choisir une politique de confidentialité adaptée. La protection de la route Flask ne prouve pas celle de l’URL distante.
- **Migrations :** `create_all()` et modifications de schéma au démarrage, plus script SQLite séparé. Introduire des migrations versionnées avant d’ajouter admissions et membres de groupe.
- **Dates :** stocker un fuseau d’événement et une échéance non ambiguë ; décider comment interpréter les anciennes dates avant conversion.
- **Tests et exploitation :** compléter les tests de permissions, concurrence, génération et erreurs réseau ; automatiser leur exécution. Aucun workflow CI trouvé dans les fichiers suivis examinés.

### P2 — Après fiabilisation

- Catalogue, demande de personnalisation, attribution et version du modèle par événement.
- Modification d’invités, recherche, pagination et import avec aperçu/validation.
- Plafond de lot côté serveur, puis traitement en arrière-plan si les volumes le justifient.
- Réduction des requêtes répétées du tableau de bord et des listes.
- Abonnements et paiements uniquement après définition du modèle commercial.

## Plan d’exécution

### Lot 1 — Stabiliser le parcours existant

- [x] Corriger les transactions de génération et les compteurs de succès.
- [x] Protéger les RSVP contre les mutations par GET en conservant les liens existants.
- [x] Valider les tailles de groupe et corriger les compteurs de personnes.
- [x] Définir le comportement des événements/comptes inactifs.
- [x] Sauvegarder et préparer la sortie des données de Git.
- [ ] Configurer et tester SMTP et Cloudinary en environnement de test.
- [x] Ajouter les tests de régression correspondant aux défauts reproduits.

**Validation :** un événement de test produit ses invitations ; une erreur au milieu du lot ne fait perdre aucun succès annoncé ; un lien RSVP exige confirmation ; un groupe invalide est refusé ; un email de récupération arrive réellement.

### Lot 2 — Livrer l’accueil et les arrivées séparées

Garder le modèle d’invitation existant pour réduire les dépendances. Son QR public peut être reconnu par le scanner authentifié sans changer les QR déjà distribués.

- [ ] Ajouter agents et affectations à un événement, avec permissions côté serveur.
- [ ] Ajouter un journal d’admissions : invitation, quantité, agent, date et identifiant de requête unique.
- [ ] Proposer des membres nominatifs facultatifs ; conserver le quota pour les groupes sans noms détaillés.
- [ ] Scanner ou rechercher, afficher les places restantes, choisir les présents, puis confirmer.
- [ ] Garantir atomiquement le quota même avec deux agents sur la dernière place.
- [ ] Rendre les nouvelles tentatives idempotentes après coupure réseau.
- [ ] Tracer les corrections avec motif ; distinguer annulation et sortie.
- [ ] Afficher personnes entrées, places restantes et groupes partiellement arrivés.
- [ ] Ajouter export réservé aux rôles autorisés.

**Validation :** invitation de deux places, une entrée à 18 h, une seconde à 19 h avec le même QR, troisième entrée refusée. Tester aussi familles, QR d’un autre événement, double clic, concurrence et réponse réseau perdue. Sans suivi des sorties, ne pas annoncer un nombre de « personnes présentes ». Ne pas confirmer d’admission hors ligne dans cette première version.

### Lot 3 — Organiser un pilote

- [ ] Déployer un environnement de test avec HTTPS et données persistantes.
- [ ] Tester sur deux téléphones, avec autorisations caméra et connexion dégradée.
- [ ] Tester au volume prévu pour l’événement, sur la base cible de production.
- [ ] Effectuer une restauration de sauvegarde et vérifier les fichiers d’invitation.
- [ ] Préparer une liste de secours et une procédure de rapprochement des entrées.
- [ ] Former les agents et réaliser une répétition avec invitations fictives.

**Validation :** parcours complet réalisé par un organisateur et deux agents, avec traitement documenté des incidents. Consigner les problèmes du pilote avant ouverture plus large.

### Lot 4 — Industrialiser la personnalisation

- [ ] Catalogue avec aperçus et choix associé à l’événement.
- [ ] Formulaire de contenu et suivi de demande dans l’administration.
- [ ] Validation du modèle personnalisé et attribution d’une version.
- [ ] Régénération contrôlée sans changement du code QR.

**Validation :** deux clients utilisent deux modèles distincts, sans accès croisé ni remplacement involontaire des fichiers de l’autre.

### Lot 5 — Préparer l’offre SaaS

- [ ] Définir la vente : par événement, prestation ou abonnement.
- [ ] Introduire limites d’usage et facturation selon ce choix.
- [ ] Mettre en place supervision, alertes, support et politique de conservation des données.
- [ ] Formaliser les procédures de déploiement, restauration et gestion des incidents.
- [ ] Valider les règles de confidentialité et les documents nécessaires avant commercialisation.

**Validation :** création d’un client, prestation, exploitation d’un événement et assistance possibles avec une procédure reproductible.

## Prochaine intervention recommandée

Commencer par le lot 1, avec la transaction de génération et les RSVP en premier. Configurer l’email pendant cette stabilisation. Développer ensuite l’accueil à partir du QR existant, avant de consacrer du temps au catalogue complet.

L’audit ne modifie pas le code applicatif. Seul ce rapport est ajouté ; aucun commit ni push n’est effectué.


## Suivi de réalisation — lot 1, 8 septembre 2026

Les défauts de génération, RSVP et quotas signalés ci-dessus sont corrigés localement. Les invitations publiques des événements inactifs ou des comptes suspendus sont désormais indisponibles. Le moteur conserve les codes QR existants et protège les fichiers de la version précédente en cas de régénération ratée.

La sauvegarde `backups/20260908T015040504252Z` a été vérifiée par empreintes et restauration SQLite temporaire. La migration locale `001_stabilisation` est appliquée ; les lignes des cinq tables métier sont inchangées. Les anciens schémas non migrés sont refusés au démarrage. Les données et fichiers générés sont exclus par `.gitignore`. Les trois bases SQLite et les douze QR suivis ont été retirés de l’index Git avec `git rm --cached` : les fichiers locaux sont conservés. Ces retraits sont préparés pour le prochain commit ; aucun historique n’a été réécrit.

Les paramètres de services sont déclarés sans secrets dans la configuration de déploiement. `check_services.py` vérifie leur présence et permet un envoi de test explicite. Les identifiants étant uniquement sur Render, l’envoi SMTP et l’upload Cloudinary réels restent à valider sur cet environnement. Ne pas considérer cette case du lot comme terminée avant réception effective du mail et téléchargement des invitations de test.

La suite compte désormais 24 tests Python, dont concurrence de génération, contraintes, reprise sur erreur, migrations et sauvegarde/restauration, ainsi que 6 contrôles JavaScript. Tous passent. Le rendu visuel n’a pas été vérifié : aucun navigateur intégré n’était disponible. Le chemin PostgreSQL de migration reste à tester sur une copie de la base cible.

Procédures détaillées : [FEATURE_NOTES.md](FEATURE_NOTES.md). Aucun déploiement, commit ou push effectué dans cette intervention.
