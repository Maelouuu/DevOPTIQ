# -*- coding: utf-8 -*-
"""Traductions anglaises des textes incrustés dans les vidéos du guide.

Clé = le texte français EXACT tel qu'il est écrit dans capture_videos.py.
Un texte absent d'ici ressort en français, et le script le signale en fin de
tournage : impossible de livrer une vidéo anglaise à moitié traduite sans le
voir passer.

Le balisage (<b>, &nbsp;) doit être conservé à l'identique.
"""

TRAD = {
    # ── Cartes-titres : puce, titre, sous-titre ───────────────────────────
    "Cartographie": "Activity map",
    "Un client demande un prix": "A customer asks for a price",
    "Par où passe la demande chez nous, et qui fait quoi ?":
        "Where does it go inside the company, and who does what?",
    "Activités": "Activities",
    "Claire part en congés": "Claire is going on leave",
    "Que faut-il savoir faire pour reprendre la cotation ?":
        "What do you need to know to take over quoting?",
    "Rôles": "Roles",
    "Préparer un entretien annuel": "Preparing an annual review",
    "La fiche de poste du Customer Service est-elle à jour ?":
        "Is the Customer Service job description up to date?",
    "Compétences": "Competencies",
    "Où en est Claire Dupont ?": "Where does Claire Dupont stand?",
    "S'évaluer sur des résultats produits, pas sur une note globale":
        "Assessing on results produced, not on an overall mark",
    "Temps · Projet": "Time · Project",
    "Combien coûte le salon ?": "How much does the trade show cost?",
    "Assembler les activités mobilisées et lire la charge réelle":
        "Assemble the activities involved and read the real workload",
    "Temps · Faiblesse": "Time · Weakness",
    "Des données client incomplètes": "Incomplete customer data",
    "Mettre un montant annuel sur un irritant que tout le monde subit":
        "Putting an annual figure on an irritant everyone puts up with",
    "Rôles · Export": "Roles · Export",
    "Le RH demande une fiche de poste": "HR asks for a job description",
    "Sortir un seul rôle, au bon format, en trois clics":
        "Pull one role, in the right format, in three clicks",
    "Cartographie · Partage": "Activity map · Sharing",
    "L'équipe doit avoir la même carte": "The team needs the same map",
    "Déposer une copie de son entité chez ses collègues":
        "Drop a copy of your entity into your colleagues' accounts",

    # ── Cartographie ──────────────────────────────────────────────────────
    "On cherche le trajet d'une <b>demande de prix</b>. On fait glisser la carte "
    "vers la gauche pour remonter au début du flux.":
        "We are tracing the path of a <b>price request</b>. Drag the map to the "
        "left to go back to the start of the flow.",
    "On zoome pour lire les <b>flèches</b> : chacune est une donnée qui passe d'une "
    "activité à la suivante. C'est ça, le flux réel.":
        "Zoom in to read the <b>arrows</b>: each one is a piece of data passing "
        "from one activity to the next. That is the real flow.",
    "L'étape qui nous intéresse est <b>Analyse de faisabilité</b>. Un clic dessus "
    "pour savoir qui la tient et ce qu'elle produit.":
        "The step we care about is <b>Feasibility analysis</b>. One click on it "
        "to see who owns it and what it produces.",
    "En trois gestes on est passé d'une carte muette à <b>la fiche d'Analyse de "
    "faisabilité</b> : ses tâches, ses données d'entrée et de sortie, ses compétences.":
        "Three gestures took us from a silent map to <b>the Feasibility analysis "
        "record</b>: its tasks, its incoming and outgoing data, its competencies.",

    # ── Activités ─────────────────────────────────────────────────────────
    "La question du jour : <b>que faut-il maîtriser pour reprendre la cotation&nbsp;?</b> "
    "On tape « cotation », la liste se réduit à l'activité concernée.":
        "Today's question: <b>what must you master to take over quoting&nbsp;?</b> "
        "Type «&nbsp;cotation&nbsp;» and the list narrows to the activity concerned.",
    "Un clic sur la barre violette déplie la fiche&nbsp;: on y voit d'abord les "
    "<b>tâches</b> et les <b>données</b> que la cotation consomme et produit.":
        "One click on the purple bar unfolds the record&nbsp;: first come the "
        "<b>tasks</b> and the <b>data</b> that quoting consumes and produces.",
    "Onglet <b>Compétences</b>&nbsp;: le résultat attendu, formulé comme on "
    "l'évaluera — « produire une cotation conforme du premier coup ».":
        "<b>Competencies</b> tab&nbsp;: the expected result, worded the way it "
        "will be assessed — «&nbsp;produce a compliant quote first time&nbsp;».",
    "Onglet <b>Savoirs</b>&nbsp;: ce qu'il faut connaître pour y arriver — ici "
    "le processus qualité ISO 9001 du site.":
        "<b>Knowledge</b> tab&nbsp;: what you need to know to get there — here "
        "the site's ISO 9001 quality process.",
    "Onglet <b>Temps</b>&nbsp;: la durée de chaque tâche. C'est ce qui alimentera "
    "le chiffrage dans la page Temps.":
        "<b>Time</b> tab&nbsp;: how long each task takes. This is what feeds the "
        "costing on the Time page.",
    "Réponse en trois clics&nbsp;: pour reprendre la cotation il faut <b>ce résultat</b>, "
    "<b>ces savoirs</b> et compter <b>ce temps-là</b>. Rien à aller chercher ailleurs.":
        "Answered in three clicks&nbsp;: to take over quoting you need <b>this "
        "result</b>, <b>this knowledge</b> and <b>that much time</b>. Nothing to "
        "look up anywhere else.",

    # ── Rôles ─────────────────────────────────────────────────────────────
    "On prépare l'entretien annuel du <b>Customer Service</b>&nbsp;: il faut sa "
    "fiche de poste à jour. On tape son nom.":
        "We are preparing the <b>Customer Service</b> annual review&nbsp;: we need "
        "an up-to-date job description. Type the role name.",
    "La fiche est déjà remplie&nbsp;: elle hérite des <b>activités</b> que ce rôle "
    "garantit dans la carte. Personne ne l'a saisie à la main.":
        "The record is already filled in&nbsp;: it inherits the <b>activities</b> "
        "this role owns on the map. Nobody typed it by hand.",
    "Seule la <b>mission</b> se rédige à la main. On y ajoute l'engagement pris cette "
    "année&nbsp;: répondre au client sous 48&nbsp;h.":
        "Only the <b>mission</b> is written by hand. We add this year's "
        "commitment&nbsp;: answer the customer within 48&nbsp;hours.",
    "<b>Activités garanties</b> puis <b>Savoirs</b>&nbsp;: c'est le contenu réel du "
    "poste, celui dont on parlera en entretien.":
        "<b>Owned activities</b> then <b>Knowledge</b>&nbsp;: this is the real "
        "content of the job, what the review will be about.",
    "La fiche de poste du Customer Service est prête pour l'entretien&nbsp;: elle a "
    "suivi la carte toute l'année, on n'a eu qu'<b>une phrase à écrire</b>.":
        "The Customer Service job description is ready for the review&nbsp;: it "
        "followed the map all year, and we only had <b>one sentence to write</b>.",

    # ── Compétences ───────────────────────────────────────────────────────
    "Entretien de <b>Claire Dupont</b>&nbsp;: on veut savoir où elle en est, résultat "
    "par résultat, avant d'en parler avec elle.":
        "<b>Claire Dupont</b>'s review&nbsp;: we want to know where she stands, "
        "result by result, before talking it through with her.",
    "Claire tient <b>plusieurs rôles</b>. On évalue toujours dans un rôle donné&nbsp;: "
    "les attendus ne sont pas les mêmes.":
        "Claire holds <b>several roles</b>. Assessment always happens inside one "
        "given role&nbsp;: expectations are not the same.",
    "On ne note pas « Claire, 3/5 »&nbsp;: on se prononce sur <b>chaque résultat "
    "qu'elle produit</b>, de 0 à 4.":
        "We do not mark «&nbsp;Claire, 3/5&nbsp;»&nbsp;: we rate <b>each result she "
        "produces</b>, from 0 to 4.",
    "Un seul résultat à 1 tire le niveau du rôle à 1&nbsp;: le global est le "
    "<b>minimum</b>, jamais une moyenne. C'est ce qui rend l'écart actionnable — "
    "on sait exactement quoi travailler.":
        "A single result at 1 pulls the role level down to 1&nbsp;: the overall "
        "level is the <b>minimum</b>, never an average. That is what makes the gap "
        "actionable — you know exactly what to work on.",

    # ── Temps · Projet ────────────────────────────────────────────────────
    "La direction demande&nbsp;: <b>combien coûte notre présence au salon&nbsp;?</b> "
    "On assemble les activités qu'il faudra mobiliser.":
        "Management asks&nbsp;: <b>how much does our presence at the trade show "
        "cost&nbsp;?</b> We assemble the activities that will be needed.",
    "Première activité&nbsp;: <b>2&nbsp;h</b> de travail, <b>1&nbsp;jour</b> d'attente "
    "avant la suite, <b>2&nbsp;personnes</b>. Le délai n'est pas du travail — il ne "
    "coûte rien.":
        "First activity&nbsp;: <b>2&nbsp;h</b> of work, <b>1&nbsp;day</b> of waiting "
        "before the next step, <b>2&nbsp;people</b>. Waiting is not work — it costs "
        "nothing.",
    "Le salon mobilise une <b>seconde activité</b>&nbsp;: on l'ajoute et on la chiffre "
    "à <b>4&nbsp;h</b>.":
        "The trade show involves a <b>second activity</b>&nbsp;: we add it and cost "
        "it at <b>4&nbsp;h</b>.",
    "La <b>charge globale</b> s'affiche&nbsp;: c'est le nombre d'heures de travail "
    "réellement engagées. Voilà le chiffre à donner à la direction.":
        "The <b>overall workload</b> appears&nbsp;: the number of working hours "
        "actually committed. That is the figure to give management.",
    "Le projet est enregistré&nbsp;: l'an prochain on repart de ce chiffrage au lieu "
    "de <b>réestimer au doigt mouillé</b>.":
        "The project is saved&nbsp;: next year we start from this costing instead of "
        "<b>guessing all over again</b>.",

    # ── Temps · Faiblesse ─────────────────────────────────────────────────
    "Tout le monde s'en plaint sans jamais le chiffrer&nbsp;: <b>les données client "
    "arrivent incomplètes</b> et il faut relancer. On va le mettre en euros.":
        "Everyone complains about it without ever costing it&nbsp;: <b>customer data "
        "arrives incomplete</b> and has to be chased up. Let's put a figure on it.",
    "L'équipe l'estime à <b>un dossier sur quatre</b>. Pas besoin de mesure "
    "exacte&nbsp;: un ordre de grandeur partagé suffit.":
        "The team puts it at <b>one file in four</b>. No exact measurement "
        "needed&nbsp;: a shared order of magnitude is enough.",
    "Quand ça arrive&nbsp;: <b>25&nbsp;min</b> de travail en plus pour relancer, et "
    "<b>120&nbsp;min</b> d'attente avant la réponse du client.":
        "When it happens&nbsp;: <b>25&nbsp;min</b> of extra work chasing it up, and "
        "<b>120&nbsp;min</b> waiting for the customer's answer.",
    "Trois estimations, un clic&nbsp;: l'application croise fréquence, temps perdu et "
    "volume annuel.":
        "Three estimates, one click&nbsp;: the application combines frequency, time "
        "lost and yearly volume.",
    "Le <b>coût annuel</b> en rouge, c'est l'irritant traduit en euros. On ne dit plus "
    "« ça nous fait perdre du temps »&nbsp;: on dit combien, et l'arbitrage se fait "
    "tout seul.":
        "The <b>annual cost</b> in red is the irritant translated into money. You no "
        "longer say «&nbsp;this wastes our time&nbsp;»&nbsp;: you say how much, and "
        "the decision makes itself.",

    # ── Export ────────────────────────────────────────────────────────────
    "Le RH demande la fiche de poste d'<b>un</b> rôle pour un recrutement. On part de "
    "<b>Exporter</b>, en haut à droite.":
        "HR asks for <b>one</b> role's job description for a hire. Start from "
        "<b>Export</b>, at the top right.",
    "On ne sort pas toute l'entité&nbsp;: on choisit <b>le rôle concerné</b>. L'export "
    "ne contiendra que lui.":
        "We are not exporting the whole entity&nbsp;: we pick <b>the role "
        "concerned</b>. The export will contain only that one.",
    "<b>HTML</b> pour l'envoyer tel quel ou l'imprimer&nbsp;; <b>Excel</b> si le RH "
    "doit retravailler le contenu.":
        "<b>HTML</b> to send it as-is or print it&nbsp;; <b>Excel</b> if HR needs to "
        "rework the content.",
    "Fiche de poste prête à envoyer, tirée de la carte&nbsp;: elle dit ce que le poste "
    "<b>fait vraiment</b>, pas ce qu'on avait écrit il y a trois ans.":
        "A job description ready to send, drawn from the map&nbsp;: it says what the "
        "job <b>actually does</b>, not what was written three years ago.",

    # ── Partage d'entité ──────────────────────────────────────────────────
    "La carte du site est finie et corrigée. Il faut maintenant que <b>l'équipe l'ait "
    "aussi</b>, sans la refaire. On ouvre la gestion des entités.":
        "The site map is finished and corrected. Now <b>the team needs it too</b>, "
        "without redoing it. Open entity management.",
    "On sélectionne l'entité à transmettre — ici <b>AFDEC Industrie</b>, celle qui "
    "porte la carte qu'on vient de terminer.":
        "Select the entity to pass on — here <b>AFDEC Industrie</b>, the one holding "
        "the map we have just finished.",
    "<b>Partager</b> n'apparaît que pour les administrateurs. On coche les collègues "
    "qui doivent travailler sur cette carte.":
        "<b>Share</b> only appears for administrators. Tick the colleagues who need "
        "to work on this map.",
    "Chacun reçoit <b>sa propre copie</b> de l'entité&nbsp;: il pourra la modifier "
    "sans toucher à l'originale.":
        "Each of them receives <b>their own copy</b> of the entity&nbsp;: they can "
        "change it without touching the original.",
    "C'est fait&nbsp;: la carte, ses activités et ses rôles sont <b>déjà dans leur "
    "compte</b>. Personne n'a eu à réimporter le fichier Visio.":
        "Done&nbsp;: the map, its activities and its roles are <b>already in their "
        "accounts</b>. Nobody had to re-import the Visio file.",
}
