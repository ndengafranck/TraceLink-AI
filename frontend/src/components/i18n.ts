import type { Lang } from "../api";

export const PANEL: Record<Lang, Record<string, string>> = {
  en: {
    title: "What the evidence supports",
    intro: "Counts come from fixed rules. The explanation is written by AI and every statement points to sightings you can check.",
    explain: "Explain the evidence", again: "Explain again", busy: "Reading the evidence…",
    stored: "sightings stored", passed: "passed", flagged: "flagged",
    writtenBy: "Written by AI", standard: "Standard summary, AI not used",
    checked: "Checked: every cited sighting exists, no invented places, no accusations.",
    next: "What to do next", cannot: "What this cannot tell you", lang: "Language",
    showSighting: "Show sighting {n} on the chart", all: "All",
    r_title: "A message to send", r_intro: "A draft for the police or your mobile operator. The AI writes only the wording; the phone details and the sighting list are added from your case. Edit it before sending.",
    r_audience: "Send to", r_police: "The police", r_operator: "My mobile operator",
    r_write: "Write the draft", r_again: "Write it again", r_busy: "Writing…", r_copy: "Copy", r_copied: "Copied",
    r_download: "Download .txt", r_imei: "The full IMEI is not stored in the draft. Write it in by hand.",
  },
  fr: {
    title: "Ce que les preuves permettent de conclure",
    intro: "Les chiffres viennent de règles fixes. L'explication est rédigée par l'IA et chaque affirmation renvoie à des signalements que vous pouvez vérifier.",
    explain: "Expliquer les preuves", again: "Expliquer à nouveau", busy: "Lecture des preuves…",
    stored: "signalements enregistrés", passed: "sans alerte", flagged: "avec alerte",
    writtenBy: "Rédigé par l'IA", standard: "Résumé standard, IA non utilisée",
    checked: "Vérifié : chaque signalement cité existe, aucun lieu inventé, aucune accusation.",
    next: "Que faire ensuite", cannot: "Ce que cela ne permet pas de savoir", lang: "Langue",
    showSighting: "Montrer le signalement {n} sur la carte", all: "Tous",
    r_title: "Un message à envoyer", r_intro: "Un brouillon pour la police ou votre opérateur mobile. L'IA ne rédige que le texte ; les détails du téléphone et la liste des signalements viennent de votre dossier. Corrigez-le avant l'envoi.",
    r_audience: "Destinataire", r_police: "La police", r_operator: "Mon opérateur mobile",
    r_write: "Rédiger le brouillon", r_again: "Rédiger à nouveau", r_busy: "Rédaction…", r_copy: "Copier", r_copied: "Copié",
    r_download: "Télécharger .txt", r_imei: "L'IMEI complet n'est pas enregistré dans le brouillon. Écrivez-le à la main.",
  },
};

export const REASONS: Record<Lang, Record<string, string>> = {
  en: {
    no_sightings: "There are no sightings to explain yet.",
    ai_not_configured: "The AI is not set up on this server.",
    ai_unavailable: "The AI service could not be reached.",
    ai_output_rejected: "The AI's answer failed our safety checks, so it was not shown.",
    ai_too_many_steps: "The AI took too many steps, so it was stopped.",
  },
  fr: {
    no_sightings: "Il n'y a pas encore de signalement à expliquer.",
    ai_not_configured: "L'IA n'est pas configurée sur ce serveur.",
    ai_unavailable: "Le service d'IA est injoignable.",
    ai_output_rejected: "La réponse de l'IA n'a pas passé nos contrôles de sécurité ; elle n'est pas affichée.",
    ai_too_many_steps: "L'IA a pris trop d'étapes ; elle a été arrêtée.",
  },
};

export const FLAGS: Record<Lang, Record<string, string>> = {
  en: {
    stale: "Over 24 hours old", low_accuracy: "Error margin over 1 km",
    implausible_movement: "Needs an impossible speed to fit its neighbours",
  },
  fr: {
    stale: "Plus de 24 heures", low_accuracy: "Marge d'erreur de plus de 1 km",
    implausible_movement: "Déplacement impossible par rapport aux voisins",
  },
};
