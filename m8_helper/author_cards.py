"""Writes the AI-authored DRAFT cards (card.v1) into m8_helper/cards/.

Every English sentence paraphrases text that was fetched with curl on 2026-11-12 from one of
three WHO pages (see SOURCES). The Kannada is drafted by an AI: status
machine_drafted_not_native_validated, clinician_reviewed=false. Nothing here is clinically
approved. Run: uv run python -m m8_helper.author_cards
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

FETCHED = "2026-11-12T10:00:00Z"
AMR = "https://www.who.int/news-room/fact-sheets/detail/antimicrobial-resistance"
PNEU = "https://www.who.int/news-room/fact-sheets/detail/pneumonia"
DIAR = "https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease"

# (id, topic_group, topic, source_url, en_text, kn_text)
CARDS = [
    (
        "amr-what-is",
        "amr",
        "what is antimicrobial (drug) resistance",
        AMR,
        "Antimicrobial resistance (AMR) happens when bacteria, viruses, fungi and parasites "
        "stop responding to medicines. Infections then become difficult or impossible to treat.",
        "ಔಷಧ ನಿರೋಧಕತೆ (AMR) ಎಂದರೆ ಬ್ಯಾಕ್ಟೀರಿಯಾ, ವೈರಸ್, ಶಿಲೀಂಧ್ರ ಮತ್ತು ಪರಾವಲಂಬಿ ಜೀವಿಗಳ ಮೇಲೆ "
        "ಔಷಧಿ ಕೆಲಸ ಮಾಡದಿರುವುದು. ಆಗ ಸೋಂಕುಗಳಿಗೆ ಚಿಕಿತ್ಸೆ ನೀಡುವುದು ಕಷ್ಟ ಅಥವಾ ಅಸಾಧ್ಯವಾಗುತ್ತದೆ.",
    ),
    (
        "amr-misuse-main-driver",
        "amr",
        "misuse of antibiotics causes resistance",
        AMR,
        "Taking antibiotics when they are not needed, or taking the wrong type, is one of the "
        "main reasons that antibiotics stop working.",
        "ಆಂಟಿಬಯಾಟಿಕ್ ಔಷಧಿಗಳನ್ನು ಅಗತ್ಯವಿಲ್ಲದಾಗ ತೆಗೆದುಕೊಳ್ಳುವುದು ಅಥವಾ ತಪ್ಪು ಬಗೆಯ ಆಂಟಿಬಯಾಟಿಕ್ "
        "ತೆಗೆದುಕೊಳ್ಳುವುದು, ಆಂಟಿಬಯಾಟಿಕ್ ಕೆಲಸ ಮಾಡದಿರಲು ಮುಖ್ಯ ಕಾರಣಗಳಲ್ಲಿ ಒಂದು.",
    ),
    (
        "amr-one-in-six",
        "amr",
        "how common is antibiotic resistance",
        AMR,
        "In 2023, about 1 in 6 laboratory-confirmed bacterial infections worldwide was resistant "
        "to antibiotic treatment. WHO estimates that in the WHO South-East Asia and Eastern "
        "Mediterranean Regions about 1 in 3 reported infections were resistant.",
        "2023ರಲ್ಲಿ ಪ್ರಪಂಚದಾದ್ಯಂತ ಪ್ರಯೋಗಾಲಯದಲ್ಲಿ ದೃಢಪಟ್ಟ ಬ್ಯಾಕ್ಟೀರಿಯಾ ಸೋಂಕುಗಳಲ್ಲಿ ಸುಮಾರು 6ರಲ್ಲಿ 1 "
        "ಆಂಟಿಬಯಾಟಿಕ್ ಚಿಕಿತ್ಸೆಗೆ ನಿರೋಧಕವಾಗಿತ್ತು. ಆಗ್ನೇಯ ಏಷ್ಯಾ ಮತ್ತು ಪೂರ್ವ ಮೆಡಿಟರೇನಿಯನ್ ಪ್ರದೇಶಗಳಲ್ಲಿ "
        "ಸುಮಾರು 3ರಲ್ಲಿ 1 ಸೋಂಕು ನಿರೋಧಕವಾಗಿತ್ತು ಎಂದು ವಿಶ್ವ ಆರೋಗ್ಯ ಸಂಸ್ಥೆ ಅಂದಾಜಿಸಿದೆ.",
    ),
    (
        "amr-causes-water-hygiene",
        "amr",
        "other causes of resistance: water, sanitation, hygiene, vaccines",
        AMR,
        "Besides inappropriate use of antibiotics, resistance spreads when clean water, sanitation "
        "and hygiene are poor, when infection prevention and control is inadequate at home, in "
        "health facilities and on farms, and when access to vaccines, diagnostics and medicines "
        "is limited.",
        "ಆಂಟಿಬಯಾಟಿಕ್ ಅನ್ನು ಸರಿಯಲ್ಲದ ರೀತಿಯಲ್ಲಿ ಬಳಸುವುದರ ಜೊತೆಗೆ, ಶುದ್ಧ ನೀರು, ನೈರ್ಮಲ್ಯ ಮತ್ತು ಸ್ವಚ್ಛತೆ "
        "ಕೊರತೆ, ಮನೆ, ಆಸ್ಪತ್ರೆ ಮತ್ತು ಕೃಷಿ ಸ್ಥಳಗಳಲ್ಲಿ ಸೋಂಕು ತಡೆಯುವ ಕ್ರಮಗಳ ಕೊರತೆ, ಹಾಗೂ ಲಸಿಕೆ ಮತ್ತು "
        "ಔಷಧಿಗಳು ಸಿಗದಿರುವುದರಿಂದ ನಿರೋಧಕತೆ ಹರಡುತ್ತದೆ.",
    ),
    (
        "pneumonia-causes",
        "pneumonia",
        "pneumonia: viruses or bacteria, antibiotics only for bacteria",
        PNEU,
        "Pneumonia can be caused by viruses, bacteria or fungi. Pneumonia caused by bacteria can "
        "be treated with antibiotics.",
        "ನ್ಯುಮೋನಿಯಾ ವೈರಸ್, ಬ್ಯಾಕ್ಟೀರಿಯಾ ಅಥವಾ ಶಿಲೀಂಧ್ರದಿಂದ ಬರಬಹುದು. ಬ್ಯಾಕ್ಟೀರಿಯಾದಿಂದ ಬಂದ "
        "ನ್ಯುಮೋನಿಯಾಕ್ಕೆ ಆಂಟಿಬಯಾಟಿಕ್ ಔಷಧಿಗಳಿಂದ ಚಿಕಿತ್ಸೆ ನೀಡಬಹುದು.",
    ),
    (
        "pneumonia-health-centre",
        "pneumonia",
        "pneumonia treatment is by prescription at a health centre",
        PNEU,
        "Most cases of pneumonia need oral antibiotics, which are often prescribed at a health "
        "centre. Hospital care is recommended only for severe cases.",
        "ಹೆಚ್ಚಿನ ನ್ಯುಮೋನಿಯಾ ಪ್ರಕರಣಗಳಿಗೆ ಬಾಯಿಯ ಮೂಲಕ ತೆಗೆದುಕೊಳ್ಳುವ ಆಂಟಿಬಯಾಟಿಕ್ ಬೇಕಾಗುತ್ತದೆ; ಇದನ್ನು "
        "ಹೆಚ್ಚಾಗಿ ಆರೋಗ್ಯ ಕೇಂದ್ರದಲ್ಲಿ ಬರೆದುಕೊಡುತ್ತಾರೆ. ಆಸ್ಪತ್ರೆ ಚಿಕಿತ್ಸೆ ತೀವ್ರ ಪ್ರಕರಣಗಳಿಗೆ ಮಾತ್ರ ಶಿಫಾರಸು.",
    ),
    (
        "pneumonia-vaccines",
        "pneumonia",
        "vaccines that prevent pneumonia",
        PNEU,
        "Immunization against Hib, pneumococcus, measles and whooping cough (pertussis) is the "
        "most effective way to prevent pneumonia.",
        "ಹಿಬ್, ನ್ಯುಮೋಕೊಕಸ್, ದಡಾರ ಮತ್ತು ಕೆಮ್ಮು ಕಫ (ಕಾಳು ಕೆಮ್ಮು) ವಿರುದ್ಧ ಲಸಿಕೆ ಹಾಕಿಸುವುದು ನ್ಯುಮೋನಿಯಾ "
        "ತಡೆಯಲು ಅತ್ಯಂತ ಪರಿಣಾಮಕಾರಿ ದಾರಿ.",
    ),
    (
        "pneumonia-nutrition-breastfeeding",
        "pneumonia",
        "nutrition and breastfeeding protect children",
        PNEU,
        "Good nutrition helps children's natural defences, starting with exclusive breastfeeding "
        "for the first 6 months of life. It also helps to shorten the illness if a child does "
        "become ill.",
        "ಸರಿಯಾದ ಪೋಷಣೆ ಮಕ್ಕಳ ಸಹಜ ರೋಗ ನಿರೋಧಕ ಶಕ್ತಿಗೆ ಸಹಾಯ ಮಾಡುತ್ತದೆ; ಮೊದಲ 6 ತಿಂಗಳು ಕೇವಲ ಎದೆಹಾಲು "
        "ನೀಡುವುದರಿಂದ ಇದು ಆರಂಭವಾಗುತ್ತದೆ. ಮಗು ಅನಾರೋಗ್ಯಕ್ಕೆ ಒಳಗಾದರೆ ಅನಾರೋಗ್ಯದ ಅವಧಿ ಕಡಿಮೆಯಾಗಲೂ ಇದು ಸಹಾಯ ಮಾಡುತ್ತದೆ.",
    ),
    (
        "pneumonia-hygiene-air",
        "pneumonia",
        "hand washing and indoor air pollution",
        PNEU,
        "Hand washing with soap, good hygiene in crowded homes and reducing indoor air "
        "pollution (for example with clean stoves) help to reduce the number of children who "
        "fall ill with pneumonia.",
        "ಸೋಪಿನಿಂದ ಕೈ ತೊಳೆಯುವುದು, ಜನಸಂದಣಿ ಇರುವ ಮನೆಗಳಲ್ಲಿ ಸ್ವಚ್ಛತೆ ಕಾಪಾಡುವುದು ಮತ್ತು ಮನೆಯೊಳಗಿನ ಹೊಗೆ "
        "ಕಡಿಮೆ ಮಾಡುವುದು (ಉದಾಹರಣೆಗೆ ಶುದ್ಧ ಒಲೆ ಬಳಸುವುದು) ನ್ಯುಮೋನಿಯಾ ಬರುವ ಮಕ್ಕಳ ಸಂಖ್ಯೆಯನ್ನು ಕಡಿಮೆ ಮಾಡುತ್ತದೆ.",
    ),
    (
        "diarrhoea-definition",
        "diarrhoea",
        "what counts as diarrhoea",
        DIAR,
        "Diarrhoea means passing 3 or more loose or liquid stools per day, or passing stools "
        "more often than is normal for the person. Frequent passing of formed stools is not "
        "diarrhoea.",
        "ದಿನಕ್ಕೆ 3 ಅಥವಾ ಹೆಚ್ಚು ಬಾರಿ ನೀರಿನಂತಹ ಅಥವಾ ಸಡಿಲ ಮಲ ಹೋಗುವುದು, ಅಥವಾ ಆ ವ್ಯಕ್ತಿಗೆ ಸಾಮಾನ್ಯಕ್ಕಿಂತ "
        "ಹೆಚ್ಚು ಬಾರಿ ಮಲ ಹೋಗುವುದನ್ನು ಅತಿಸಾರ (ಬೇಧಿ) ಎನ್ನುತ್ತಾರೆ. ಗಟ್ಟಿ ಮಲ ಪದೇ ಪದೇ ಹೋಗುವುದು ಅತಿಸಾರ ಅಲ್ಲ.",
    ),
    (
        "diarrhoea-ors",
        "diarrhoea",
        "ORS for diarrhoea",
        DIAR,
        "Oral rehydration salts (ORS) solution is a mixture of clean water, salt and sugar. It "
        "replaces the water and salts lost in the stool and is a key treatment for diarrhoea.",
        "ಓಆರ್ಎಸ್ (ಬಾಯಿಯ ಮೂಲಕ ನೀರಿನ ಅಂಶ ತುಂಬುವ ಲವಣ) ದ್ರಾವಣ ಶುದ್ಧ ನೀರು, ಉಪ್ಪು ಮತ್ತು ಸಕ್ಕರೆಯ ಮಿಶ್ರಣ. "
        "ಇದು ಮಲದಲ್ಲಿ ಕಳೆದುಹೋದ ನೀರು ಮತ್ತು ಲವಣಗಳನ್ನು ಮರಳಿ ತುಂಬುತ್ತದೆ; ಅತಿಸಾರದ ಮುಖ್ಯ ಚಿಕಿತ್ಸೆ.",
    ),
    (
        "diarrhoea-zinc",
        "diarrhoea",
        "zinc supplements for diarrhoea",
        DIAR,
        "Zinc supplements reduce how long a diarrhoea episode lasts by 25% and are associated "
        "with a 30% reduction in stool volume.",
        "ಜಿಂಕ್ ಪೂರಕಗಳು ಅತಿಸಾರದ ಅವಧಿಯನ್ನು ಶೇಕಡಾ 25ರಷ್ಟು ಕಡಿಮೆ ಮಾಡುತ್ತವೆ ಮತ್ತು ಮಲದ ಪ್ರಮಾಣ ಶೇಕಡಾ 30ರಷ್ಟು "
        "ಕಡಿಮೆಯಾಗಲು ಸಂಬಂಧಿಸಿವೆ.",
    ),
    (
        "diarrhoea-continue-feeding",
        "diarrhoea",
        "keep eating and breastfeeding during diarrhoea",
        DIAR,
        "Continue giving nutrient-rich foods, including breast milk, during a diarrhoea episode.",
        "ಅತಿಸಾರ ಇರುವಾಗಲೂ ಎದೆಹಾಲು ಸೇರಿದಂತೆ ಪೌಷ್ಟಿಕ ಆಹಾರವನ್ನು ಮುಂದುವರಿಸಿ ನೀಡಿ.",
    ),
    (
        "diarrhoea-see-health-professional",
        "diarrhoea",
        "when to see a health professional for diarrhoea",
        DIAR,
        "See a health professional if diarrhoea persists, if there is blood in the stool, or if "
        "there are signs of dehydration.",
        "ಅತಿಸಾರ ಮುಂದುವರಿದರೆ, ಮಲದಲ್ಲಿ ರಕ್ತ ಇದ್ದರೆ ಅಥವಾ ದೇಹದಲ್ಲಿ ನೀರಿನ ಕೊರತೆಯ ಲಕ್ಷಣಗಳಿದ್ದರೆ "
        "ಆರೋಗ್ಯ ಕಾರ್ಯಕರ್ತರನ್ನು ಅಥವಾ ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ.",
    ),
    (
        "diarrhoea-prevention-hygiene-water",
        "diarrhoea",
        "preventing diarrhoea: safe water, sanitation, hand washing",
        DIAR,
        "Key ways to prevent diarrhoea include safe drinking-water, improved sanitation, hand "
        "washing with soap, good personal and food hygiene, and exclusive breastfeeding for the "
        "first 6 months of life.",
        "ಅತಿಸಾರ ತಡೆಯಲು ಸುರಕ್ಷಿತ ಕುಡಿಯುವ ನೀರು, ಉತ್ತಮ ನೈರ್ಮಲ್ಯ, ಸೋಪಿನಿಂದ ಕೈ ತೊಳೆಯುವುದು, ವೈಯಕ್ತಿಕ ಮತ್ತು "
        "ಆಹಾರ ಸ್ವಚ್ಛತೆ, ಮತ್ತು ಮೊದಲ 6 ತಿಂಗಳು ಕೇವಲ ಎದೆಹಾಲು ನೀಡುವುದು ಮುಖ್ಯ.",
    ),
    (
        "diarrhoea-rotavirus-vaccine",
        "diarrhoea",
        "rotavirus vaccine",
        DIAR,
        "Rotavirus vaccination is one of the key measures to prevent diarrhoea.",
        "ರೋಟಾವೈರಸ್ ಲಸಿಕೆ ಅತಿಸಾರ ತಡೆಯುವ ಮುಖ್ಯ ಕ್ರಮಗಳಲ್ಲಿ ಒಂದು.",
    ),
]


def build() -> list[dict]:
    out = []
    for cid, _grp, topic, url, en, kn in CARDS:
        out.append(
            {
                "schema_version": "card.v1",
                "id": cid,
                "topic": topic,
                "kn_text": unicodedata.normalize("NFC", kn),
                "en_text": en,
                "source_url": url,
                "source_retrieved_at": FETCHED,
                "version": 1,
                "status": "machine_drafted_not_native_validated",
                "clinician_reviewed": False,
            }
        )
    return out


def main() -> None:
    d = Path(__file__).parent / "cards"
    d.mkdir(exist_ok=True)
    for c in build():
        (d / f"{c['id']}.json").write_text(
            json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"wrote {len(CARDS)} cards to {d}")


if __name__ == "__main__":
    main()
