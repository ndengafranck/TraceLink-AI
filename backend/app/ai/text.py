"""Fixed wording in English and French.

Everything the product says WITHOUT the model (fallback explanation, notices,
report layout) lives here, so both languages stay consistent and reviewable.
"""

from typing import Literal

Language = Literal["en", "fr"]
LANGUAGE_NAME = {"en": "English", "fr": "French"}

FLAG_WHY = {
    "en": {
        "stale": "older than 24 hours, so the phone may have moved since",
        "low_accuracy": "reported with a position error above 1 km",
        "implausible_movement": "would need an impossible speed to fit with a neighbouring sighting",
    },
    "fr": {
        "stale": "datent de plus de 24 heures, le téléphone a pu bouger depuis",
        "low_accuracy": "indiquent une marge d'erreur de plus de 1 km",
        "implausible_movement": "exigeraient une vitesse impossible par rapport à un signalement voisin",
    },
}

T = {
    "en": {
        "none_headline": "No sightings have been received for this case yet.",
        "none_uncertainty": "With no sightings there is nothing to explain or locate.",
        "headline": "{n} sighting(s) stored; {c} without flags.",
        "passed": "{n} sighting(s) passed every automatic check.",
        "flagged": "{n} sighting(s) are flagged '{flag}': {why}.",
        "guidance": [
            "Do not go to a location alone to look for the phone. Share it with local police.",
            "Contact your mobile operator to block the SIM and ask about blocking the device.",
            "Change the passwords of accounts that were signed in on the phone.",
            "Open this case again if new sightings arrive; they are checked the same way.",
        ],
        "uncertainty": [
            "A sighting shows where a finder device was, not who has the phone.",
            "Flagged sightings need extra caution before you rely on them.",
        ],
        "simulated_uncertainty": "These sightings are simulated demo data, not real detections.",
        "notice_base": "Sightings are reports to check, not proof of where the phone is or who holds it.",
        "notice_sim": "These sightings are SIMULATED demo data, not real detections. ",
    },
    "fr": {
        "none_headline": "Aucun signalement n'a encore été reçu pour ce dossier.",
        "none_uncertainty": "Sans signalement, il n'y a rien à expliquer ni à localiser.",
        "headline": "{n} signalement(s) enregistré(s) ; {c} sans alerte.",
        "passed": "{n} signalement(s) ont passé tous les contrôles automatiques.",
        "flagged": "{n} signalement(s) ont l'alerte « {flag} » : ils {why}.",
        "guidance": [
            "N'allez pas seul(e) chercher le téléphone. Transmettez le dossier à la police.",
            "Contactez votre opérateur mobile pour bloquer la carte SIM et demander le blocage de l'appareil.",
            "Changez les mots de passe des comptes connectés sur le téléphone.",
            "Rouvrez ce dossier si de nouveaux signalements arrivent : ils sont vérifiés de la même façon.",
        ],
        "uncertainty": [
            "Un signalement montre où se trouvait un appareil détecteur, pas qui a le téléphone.",
            "Les signalements avec alerte demandent plus de prudence avant d'être utilisés.",
        ],
        "simulated_uncertainty": "Ces signalements sont des données de démonstration simulées, pas de vraies détections.",
        "notice_base": "Les signalements sont des informations à vérifier : ils ne prouvent ni où se trouve le téléphone ni qui l'a.",
        "notice_sim": "Ces signalements sont SIMULÉS (données de démonstration), pas de vraies détections. ",
    },
}

# ---- report draft layout (built by code; the model only writes the narrative) ----
R = {
    "en": {
        "title": {"police": "Lost phone report for the police", "operator": "Lost phone request to my mobile operator"},
        "phone": "PHONE",
        "model": "Model",
        "nickname": "Nickname",
        "imei": "IMEI",
        "imei_value": "ending {last4} (write the full 15 digits here: _______________)",
        "ownership": "Ownership check",
        "own_demo": "DEMO check only, not a real verification",
        "own_phone": "code shown on the phone itself",
        "own_none": "not completed",
        "opened": "Case opened",
        "summary": "SUMMARY",
        "sightings": "SIGHTINGS ({n} stored, {p} without flags, {f} flagged). Times are UTC.",
        "no_sightings": "No sightings have been received.",
        "more": "... and {n} more not listed.",
        "no_flags": "no flags",
        "error": "error {m} m",
        "ask": "WHAT I AM ASKING",
        "note": "NOTE",
        "footer": "Sightings are reports to check, not proof of where the phone is or who holds it. Prepared with TraceLink; please edit before sending.",
        "sim_note": "The sightings listed are SIMULATED demo data, not real detections.",
        "flags": {"stale": "over 24 h old", "low_accuracy": "error over 1 km", "implausible_movement": "impossible movement"},
        "fallback_summary": "My phone was reported lost on the date shown. {n} sighting(s) are listed below; {p} passed the automatic checks and {f} were flagged. A sighting shows where a finder device was, not who has the phone.",
        "fallback_ask": {
            "police": ["Please record this report.", "Please tell me what else you need to open an investigation."],
            "operator": ["Please block the SIM card.", "Please block the device by IMEI.", "Please confirm in writing when it is done."],
        },
    },
    "fr": {
        "title": {"police": "Déclaration de perte de téléphone à la police", "operator": "Demande à mon opérateur mobile : téléphone perdu"},
        "phone": "TÉLÉPHONE",
        "model": "Modèle",
        "nickname": "Surnom",
        "imei": "IMEI",
        "imei_value": "se terminant par {last4} (écrire ici les 15 chiffres : _______________)",
        "ownership": "Vérification de propriété",
        "own_demo": "vérification de DÉMONSTRATION seulement, pas une vraie vérification",
        "own_phone": "code affiché sur le téléphone lui-même",
        "own_none": "non terminée",
        "opened": "Dossier ouvert",
        "summary": "RÉSUMÉ",
        "sightings": "SIGNALEMENTS ({n} enregistrés, {p} sans alerte, {f} avec alerte). Heures en UTC.",
        "no_sightings": "Aucun signalement n'a été reçu.",
        "more": "... et {n} autres non listés.",
        "no_flags": "aucune alerte",
        "error": "erreur {m} m",
        "ask": "CE QUE JE DEMANDE",
        "note": "REMARQUE",
        "footer": "Les signalements sont des informations à vérifier : ils ne prouvent ni où se trouve le téléphone ni qui l'a. Préparé avec TraceLink ; à corriger avant l'envoi.",
        "sim_note": "Les signalements listés sont des données de démonstration SIMULÉES, pas de vraies détections.",
        "flags": {"stale": "plus de 24 h", "low_accuracy": "erreur de plus de 1 km", "implausible_movement": "mouvement impossible"},
        "fallback_summary": "Mon téléphone a été déclaré perdu à la date indiquée. {n} signalement(s) sont listés ci-dessous ; {p} ont passé les contrôles automatiques et {f} ont une alerte. Un signalement montre où se trouvait un appareil détecteur, pas qui a le téléphone.",
        "fallback_ask": {
            "police": ["Merci d'enregistrer cette déclaration.", "Merci de m'indiquer ce qu'il faut de plus pour ouvrir une enquête."],
            "operator": ["Merci de bloquer la carte SIM.", "Merci de bloquer l'appareil grâce à son IMEI.", "Merci de me confirmer par écrit quand c'est fait."],
        },
    },
}
