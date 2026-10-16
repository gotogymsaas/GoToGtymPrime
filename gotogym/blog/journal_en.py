"""English version of the Journal entries (title, excerpt and body), keyed by slug.

The Spanish text in `journal_content.py` is the original; this is its
translation. `Post` uses these when the active language is English (see
`Post.titulo`, `Post.resumen` and `Post.cuerpo`). Same format as the original:
`## ` for subheadings, lines starting with `- ` for lists, `[n]` to cite
reference n.
"""

TRADUCCIONES = {
    'grafeno-el-material-de-un-solo-atomo-de-espesor': {
        'title': 'Graphene: the material one atom thick',
        'excerpt': (
            'A single layer of carbon atoms, isolated in 2004 and awarded the Nobel Prize in 2010, brings together '
            'properties that no conventional fiber matches. Here is what is known and what must not be promised.'
        ),
        'content': '''In 2004, a team at the University of Manchester led by Andre Geim and Konstantin Novoselov published in Science how to isolate and measure carbon films one atom thick [1]. Six years later they received the Nobel Prize in Physics "for groundbreaking experiments regarding the two-dimensional material graphene" [2].

## What it is, precisely

The ISO/TS 80004-13 standard defines graphene as a single layer of carbon atoms with sp² hybridization [3]. When between three and ten layers are stacked it is called few-layer graphene [4], and when there are many, graphite, the same material as the lead in a pencil.

This precision matters outside the lab: in textile practice it is common to work with derivatives, such as graphene oxide or reduced graphene oxide, whose behavior is not identical to that of the ideal sheet [8].

## Four properties that explain the interest

- **Strength.** In suspended single-layer sheets, a Young's modulus of 1.0 TPa and an intrinsic strength of 130 GPa were measured [5].
- **Heat.** Its thermal conductivity at room temperature was measured at between 4,840 and 5,300 W/m·K [6], compared with about 401 W/m·K for copper [7].
- **Light.** A single layer absorbs 2.3 % of the white light that reaches it, a value set by a fundamental constant of physics [9].
- **Electricity.** The first studies already showed electron mobilities of about 10,000 cm²/V·s at room temperature [1].

## From the ideal sheet to the garment

All those figures correspond to nearly perfect monolayers, measured under laboratory conditions. A garment is not that. In a textile, graphene appears as a coating on the fabric [10][11], as part of a composite fiber [12] or as a film laminated onto a fabric [13], and the final result depends on how much material there is, in what form, and how well it sticks to the fiber after the garment is worn and washed.

That is why the value of graphene for sportswear is not in a record figure, but in the specific functions that can be measured in a finished garment: heat management, conductivity for sensors, durability. We talk about each of them in the next entries.

## Why we follow it closely

At GoToGym we review materials science to separate what is proven from what is still a promise. What is claimed about a specific garment is stated on its product page; this article describes the state of the science, not the properties of any particular item.''',
    },
    'cuando-una-prenda-conduce-el-calor-grafeno-y-gestion-termica': {
        'title': 'When a garment conducts heat: graphene and thermal management',
        'excerpt': (
            'Graphene conducts heat better than almost any known material. What that means in a fabric, what has been '
            'shown in prototypes and where the limits are.'
        ),
        'content': '''Training generates heat. How clothing handles it, whether it dissipates it, spreads it or holds it in, changes the feeling of comfort. That is why thermal management is the area where graphene in textiles is most researched.

## The starting point

In a suspended graphene monolayer, a thermal conductivity of between 4,840 and 5,300 W/m·K was measured at room temperature [1], more than ten times that of copper, which is around 401 W/m·K [2]. Hence the idea: a fabric with graphene could spread body heat more evenly.

## Two ways to use it

- **Passive: spreading heat.** Graphene built into the fabric helps spread heat from the areas where it builds up. Reviews of graphene textiles for thermal management and flame retardancy cover this line of work [3].
- **Active: generating heat.** Since graphene conducts electricity and converts electrical energy into heat through the Joule effect, coated fabrics have been developed that work as flexible heating elements for garments with personalized heating or therapeutic use [4]. They need a power source, usually a small battery.

## What is still a challenge

- **From the lab to the fabric.** The record figure is for an ideal sheet. In a fabric, the effective conductivity depends on the amount of graphene, its shape and how it connects between fibers.
- **Washing.** Whether the effect survives dozens of washes is an active research problem; there is work focused specifically on wash-resistant textile heaters [5].
- **Comfort.** A garment must remain flexible, breathable and soft. A coating that improves one metric and worsens the feel is no good for training.

## How to read a thermal claim

When a garment promises to "regulate temperature", it is worth asking what was measured (conductivity, skin temperature, drying time), with what method and after how many washes. A promise without those answers is advertising, not product engineering.''',
    },
    'corres-mas-con-grafeno-lo-que-dice-un-ensayo-en-humanos': {
        'title': 'Do you run faster with graphene? What a human trial says (and does not say)',
        'excerpt': (
            'A test with people: a randomized double-blind trial with graphene compression garments. Results, limits '
            'and how to interpret them honestly.'
        ),
        'content': '''Performance claims are the ones most prone to excess. That is why it is worth looking in detail at a test with real people.

## The study

In 2025, a research team published in Sports Medicine - Open a randomized, crossover, double-blind trial [1]. Data from 15 male university students (of 20 recruited), aged 18 to 22 and physically active, were analyzed. Each did two incremental treadmill tests seven days apart: one wearing a compression shirt and pants made with composite nylon and graphene fibers (infrared emissivity of 0.88, above the standard's minimum of 0.83), and another wearing identical garments without graphene.

## What they found

- **Duration of effort.** 791.9 s with graphene versus 753.5 s with the control garment: 38.4 s longer, or about 5 %.
- **Maximum heart rate.** Slightly lower with graphene (198.8 versus 200.3 beats per minute).
- **Maximal oxygen uptake (VO₂max).** No significant difference between the two conditions.

The authors conclude that the garments improved aerobic capacity and reduced cardiac load [1].

## What it does not say

- **It is a single, small study.** Fifteen people, all male and recreationally active. The authors themselves point out the small sample size.
- **The mechanism was not measured.** The work attributes the effect to far-infrared emission, but it did not record skin temperature or core temperature, nor blood flow, nor the actual pressure of the compression.
- **Blinding was not checked.** It was not assessed whether participants could guess which garment they were wearing.

## How we read it

It is a promising result and a hypothesis that deserves to be replicated with more people, with women and with athletes of different levels, measuring the mechanism. It is not a guarantee that a garment will "make you perform better". We prefer to say exactly that, and wait for the evidence to grow before turning it into a promise.''',
    },
    'prendas-que-sienten-sensores-textiles-de-grafeno': {
        'title': 'Garments that sense: graphene textile sensors',
        'excerpt': (
            'Joint movement and body signals: graphene makes it possible to integrate thin, flexible sensors into the '
            'fabric itself. What has been achieved and what is missing for it to leave the lab.'
        ),
        'content': '''A traditional sensor is worn. A textile sensor is part of the garment. Graphene, thanks to its atomic thickness and its conductivity, is one of the most studied materials for achieving this.

## What it can measure

Reviews of graphene sensors for health monitoring describe non-invasive, wearable applications [1]. In textiles, the published prototypes have been tested on detecting human movement, such as that of the joints [2][3].

Some published examples, which depend greatly on the design of each sensor and are not typical values [1]:

- Pressure sensors with sensitivities of 0.82 and 25.1 kPa⁻¹.
- Strain sensors with gauge factors of 25.2 and 502.
- Flexible electrodes that tolerate more than 40 % stretch.

## Why graphene

The review notes that its high specific surface area and atomic thickness explain the sensitivity, and that its flexibility and thinness allow close, conformal contact with the skin [1]. In sports, this opens the door to analyzing movement technique without wires or separate devices.

## What is missing

- **Durability.** The same authors identify sensor longevity as a pending problem [1].
- **Biocompatibility.** Debates remain because of the great heterogeneity of graphene-based materials, and data on long-term accumulation effects are lacking [1].
- **From prototype to product.** Power, electronics, washing and calibration are engineering challenges as important as the material.

## What to expect

It is a field with real, published advances, but mostly at the prototype stage. A garment with graphene sensors ready for everyday use requires solving those points, not just having a sensitive material. When we do, we will say so with data.''',
    },
    'antibacteriano-y-seguro-separar-evidencia-y-marketing-en-el-grafeno': {
        'title': 'Antibacterial and safe: separating evidence from marketing in graphene',
        'excerpt': (
            'Graphene harms bacteria in the lab, but that is not the same as an antibacterial garment. What science says '
            'about antimicrobial activity and about safety, and how to read a label.'
        ),
        'content': '''"Antibacterial" is one of the most used words in sportswear. With graphene it often appears, and it is worth understanding where it comes from and how far it goes.

## What was shown

A 2010 paper in ACS Nano studied the toxicity of graphene and graphene oxide sheets toward bacteria and found that these materials were harmful to them [1]. That much-cited work fueled later research on textiles with antibacterial activity.

## Why it is not enough

- **It is a lab assay.** It was done with graphene sheets and films prepared for the experiment, not with a garment that has been worn and washed.
- **Shape matters.** Another study shows that the antibacterial activity of graphene oxide can change depending on how its sheets are aligned [2].
- **Graphene is not just one thing.** Its biological behavior depends on the oxidation state, the size of the sheets and how it was prepared [3].

The honest conclusion is that there is a scientific basis for investigating the antibacterial function, not an automatic guarantee for any garment "with graphene".

## Safety: what is known

The European research program Graphene Flagship summarizes that graphene and layered materials are generally safe if handled properly, and that safety depends on the specific properties of the material and the conditions of exposure [3]. Among its findings:

- On the skin, only high concentrations with long exposures produced membrane damage; skin toxicity turns out to be low.
- In the lungs, nanometer-sized graphene oxide particles proved safe, while larger ones may cause adverse effects.
- In chronically exposed workers, no significant immune response was observed.

A life-cycle analysis of graphene textiles for fire protection equipment placed the greatest exposure risks in manufacturing, through inhalation, and not in use, because once integrated into the product it is very hard for particles to be released [4]. It is a reminder that safety is also the responsibility of whoever manufactures. There are broader reviews on health and the environment [5].

## How to read a label

When facing a garment that says "antibacterial" or "with graphene", it is worth asking:

- What form of graphene does it contain (monolayer, few layers, oxide) and in what proportion?
- With what method was the antibacterial activity measured? There is a specific standard for textiles, ISO 20743 [6].
- Was it measured after washing the garment and how many times?

If there are no answers, the word is just a word.''',
    },
    'ropa-deportiva-funcionalizada-como-se-disena-la-respuesta-de-una-tela': {
        'title': 'Functionalized sportswear: how a fabric\'s response is designed',
        'excerpt': (
            'Moisture, temperature, sensing: a "functional" fabric is the sum of fibers, structure and finishes. A map of '
            'the strategies and of where graphene fits.'
        ),
        'content': '''Functionalizing a textile means giving it a function that the fiber alone does not have. It is achieved at different levels: inside the fiber, in the yarn, in the structure of the weave or with a finish on the fabric. Each level has advantages and costs.

## Three functions that matter when training

- **Moisture management.** The strategy is capillarity: microscopic channels between the fibers that carry sweat away from the skin to the surface of the fabric, where it evaporates.
- **Thermal management.** Besides the conductivity of the fibers and the porosity of the fabric, phase change materials (PCM) are used, which absorb or release latent heat in a narrow temperature range. Their known limitation is low thermal conductivity and the risk of leaks [2].
- **Sensing and conductivity.** Conductive materials come in here, among them graphene, to measure movement or generate heat.

## Where graphene fits

It does not replace the other strategies, it complements them. Work on graphene textiles for thermal management [3] and reviews on textile materials in sport [1] show a picture of combinations, not of a single solution.

## Principles for designing a functional garment

- **One function, one metric.** If quick drying is promised, drying must be measured; if regulating heat is promised, temperature or conductivity.
- **Durability as a requirement.** A function that disappears after five washes is not a function.
- **Comfort first.** Feel, elasticity and breathability are not negotiable.
- **Proportional evidence.** A lab result is communicated as a lab result.

## What is coming

The trend is to combine functions in a single garment and validate them with human tests, not only in the lab. It is the standard with which we want to look at every new material.''',
    },
}

# Referencias: anotaciones en espanol dentro del texto de la referencia.
REFERENCIAS = {
    'NobelPrize.org. The Nobel Prize in Physics 2010 (A. Geim y K. Novoselov): "for groundbreaking experiments regarding the two-dimensional material graphene".':
        'NobelPrize.org. The Nobel Prize in Physics 2010 (A. Geim and K. Novoselov): "for groundbreaking experiments regarding the two-dimensional material graphene".',
    'ISO/TS 80004-13:2017 (muestra de la norma, definiciones de grafeno y grafeno de pocas capas).':
        'ISO/TS 80004-13:2017 (sample of the standard, definitions of graphene and few-layer graphene).',
    'Langley Alloys. What is the thermal conductivity of copper? (valor de referencia: 401 W/m·K a 20 °C).':
        'Langley Alloys. What is the thermal conductivity of copper? (reference value: 401 W/m·K at 20 °C).',
}
