# Contrat de mise à disposition pour évaluation — OptiqFluent

> **PROJET DE CONTRAT — à faire relire et valider par un juriste avant signature.**
> Ce document reflète les choix techniques de la distribution beta (image Docker
> sur l'infrastructure du Client, licence logicielle à expiration).

Entre :

**AFDEC**, [forme juridique, capital, siège social, RCS], représentée par
[Mael Girardin], ci-après « **le Fournisseur** »,

et

**[RAISON SOCIALE DU CLIENT]**, [forme juridique, siège social, RCS],
représentée par [nom, fonction], ci-après « **le Client** »,

## Article 1 — Objet

Le Fournisseur met à la disposition du Client, à titre d'évaluation, le
logiciel **OptiqFluent** (ci-après « le Logiciel »), application de gestion des
compétences et activités, sous forme d'une image logicielle (conteneur Docker)
exécutée sur l'infrastructure du Client. Le présent contrat a pour objet de
définir les conditions de cette mise à disposition.

## Article 2 — Durée

2.1. Le Logiciel est mis à disposition pour une **période d'évaluation de
[1 (un)] mois** à compter de la remise de la licence visée à l'article 5,
renouvelable par accord écrit des parties (y compris par email).

2.2. À l'issue de la période d'évaluation, les parties pourront conclure un
contrat d'abonnement définissant les conditions d'un usage pérenne. À défaut,
le présent contrat prend fin dans les conditions de l'article 9.

## Article 3 — Licence d'utilisation

3.1. Le Fournisseur concède au Client, pour la durée du contrat, un droit
d'utilisation **personnel, non exclusif, non transférable et non
sous-licenciable** du Logiciel, pour ses **besoins internes d'évaluation
uniquement**, sur une seule instance.

3.2. Sont expressément interdits, sauf autorisation écrite préalable du
Fournisseur ou exception légale impérative :
- toute copie du Logiciel autre que les copies techniques strictement
  nécessaires à son exécution et à la sauvegarde ;
- toute mise à disposition de tiers, revente, location, prêt ou hébergement
  pour le compte de tiers ;
- toute décompilation, désassemblage, rétro-ingénierie, extraction de tout ou
  partie du code source, des invites (« prompts ») d'intelligence artificielle
  ou de la structure de la base de données, au-delà de ce que l'article
  L.122-6-1 du Code de la propriété intellectuelle autorise impérativement ;
- toute modification, adaptation, correction ou création d'œuvre dérivée ;
- toute suppression ou tout contournement du **mécanisme de licence à
  expiration** intégré au Logiciel, ou de toute autre mesure technique de
  protection.

3.3. Le Client est informé que le Logiciel intègre un mécanisme de licence
signée comportant une date d'expiration. Ce mécanisme ne collecte ni ne
transmet aucune donnée du Client.

## Article 4 — Propriété intellectuelle

4.1. Le Logiciel, son code source, son interface, sa documentation, ses invites
d'IA, sa marque et tous les éléments qui le composent demeurent la **propriété
exclusive du Fournisseur**. Le présent contrat n'opère aucun transfert de
propriété intellectuelle.

4.2. Les **données saisies ou importées par le Client** dans le Logiciel
demeurent la **propriété exclusive du Client**. Elles sont hébergées sur
l'infrastructure du Client ; le Fournisseur n'y a pas accès.

## Article 5 — Modalités de mise à disposition

5.1. Le Fournisseur remet au Client : (a) un accès en lecture au registre
d'images privé, (b) un fichier de licence signé, (c) la documentation
d'installation, (d) les fichiers de configuration types.

5.2. Le Client fait son affaire, à ses frais, des **moyens d'exécution**
nécessaires, à savoir :
- l'infrastructure d'hébergement (machine ou serveur exécutant Docker) ;
- la **base de données PostgreSQL** (conteneur local fourni dans la
  configuration type, ou service hébergé de son choix) ainsi que ses
  sauvegardes ;
- un **abonnement à l'API OpenAI** et la clé associée, nécessaires aux
  fonctions d'intelligence artificielle du Logiciel — la consommation
  correspondante est facturée au Client directement par OpenAI ;
- le cas échéant, un compte de messagerie pour l'envoi des emails de
  réinitialisation de mot de passe.

5.3. Le Fournisseur pourra livrer des **mises à jour** du Logiciel pendant la
période d'évaluation via le registre. Le Client les installe selon la
procédure documentée ; les données et la configuration sont conservées.

## Article 6 — Assistance

Pendant la période d'évaluation, le Fournisseur fournit une assistance
raisonnable par email à [afdec.enterprise.services@gmail.com], en jours
ouvrés, sans engagement de niveau de service.

## Article 7 — Confidentialité

7.1. Chaque partie s'engage à garder confidentiels les informations et
documents de l'autre partie auxquels elle aurait accès à l'occasion du
contrat — notamment, pour le Fournisseur : les données, processus et
organisations du Client ; pour le Client : le Logiciel, sa conception, sa
documentation et les conditions du présent contrat.

7.2. Cette obligation survit [3 (trois)] ans à la fin du contrat.

7.3. Le Client est informé que les fonctions d'IA transmettent les contenus
concernés à l'API OpenAI **via le compte OpenAI du Client**, selon les
conditions et la politique de confidentialité d'OpenAI, sans transiter par le
Fournisseur.

## Article 8 — Garanties et responsabilité

8.1. Le Logiciel est fourni **« en l'état »** à des fins d'évaluation, sans
garantie de disponibilité, de performance ni d'adéquation à un besoin
particulier.

8.2. Le Client reste seul responsable de son infrastructure, de ses
sauvegardes et de la conformité de ses traitements de données (notamment RGPD)
en sa qualité de responsable de traitement ; le Fournisseur n'accède pas aux
données du Client et n'agit pas comme sous-traitant au sens du RGPD.

8.3. La responsabilité totale du Fournisseur au titre du présent contrat est
plafonnée à [montant symbolique / montant payé, le cas échéant]. Aucune partie
ne répond des dommages indirects.

## Article 9 — Fin du contrat

9.1. À l'expiration de la période d'évaluation (ou en cas de résiliation pour
manquement, après mise en demeure restée sans effet [15] jours), le Client :
- cesse toute utilisation du Logiciel ;
- **supprime l'image Docker, ses copies et le fichier de licence** de ses
  systèmes et le confirme par écrit ;
- conserve l'entière propriété de ses données, qu'il peut exporter au
  préalable (fonctions d'export intégrées) ou extraire de sa base PostgreSQL.

9.2. L'expiration technique de la licence à la date convenue ne constitue pas
un dysfonctionnement du Logiciel.

## Article 10 — Divers

Contrat soumis au **droit français**. Compétence : tribunaux de [ville].
Toute modification requiert un avenant écrit signé des deux parties.

Fait à [ville], le [date], en deux exemplaires.

| Pour AFDEC | Pour [CLIENT] |
|---|---|
| [Nom, signature] | [Nom, signature] |
