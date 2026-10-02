"""Entradas del Journal sobre materiales avanzados y ropa deportiva
funcionalizada. Las carga el comando `seed_journal`.

Formato del contenido (ver `blog_extras.post_body`): `## ` para subtitulos,
lineas con `- ` para listas, `[n]` para citar la referencia n de la entrada.
Cada referencia es "texto | url". Todo dato numerico de aqui sale de la
fuente citada junto a el.
"""

NOVOSELOV_2004 = (
    'Novoselov, K. S., Geim, A. K., Morozov, S. V., Jiang, D., Zhang, Y., Dubonos, S. V., '
    'Grigorieva, I. V., Firsov, A. A. (2004). Electric Field Effect in Atomically Thin Carbon Films. '
    'Science 306(5696), 666-669. | '
    'https://www.semanticscholar.org/paper/Electric-Field-Effect-in-Atomically-Thin-Carbon-Novoselov-Geim/'
    'c92bd747a97eeafdb164985b0d044caa1dc6e73e'
)
NOBEL_2010 = (
    'NobelPrize.org. The Nobel Prize in Physics 2010 (A. Geim y K. Novoselov): "for groundbreaking experiments '
    'regarding the two-dimensional material graphene". | '
    'https://www.nobelprize.org/prizes/physics/2010/illustrated-information/'
)
ISO_80004 = (
    'ISO/TS 80004-13:2024. Nanotechnologies - Vocabulary - Part 13: Graphene and other two-dimensional (2D) '
    'materials. | https://www.iso.org/obp/ui/#iso:std:iso:ts:80004:-13:ed-2:v1:en'
)
ISO_80004_2017 = (
    'ISO/TS 80004-13:2017 (muestra de la norma, definiciones de grafeno y grafeno de pocas capas). | '
    'https://cdn.standards.iteh.ai/samples/64741/47fb2d4f20aa4801a560bb8cb38f6e8e/ISO-TS-80004-13-2017.pdf'
)
LEE_2008 = (
    'Lee, C., Wei, X., Kysar, J. W., Hone, J. (2008). Measurement of the Elastic Properties and Intrinsic '
    'Strength of Monolayer Graphene. Science 321(5887), 385-388. doi:10.1126/science.1157996 | '
    'https://www.science.org/doi/10.1126/science.1157996'
)
BALANDIN_2008 = (
    'Balandin, A. A., Ghosh, S., Bao, W., Calizo, I., Teweldebrhan, D., Miao, F., Lau, C. N. (2008). '
    'Superior thermal conductivity of single-layer graphene. Nano Letters 8(3), 902-907. | '
    'https://pubmed.ncbi.nlm.nih.gov/18284217/'
)
NAIR_2008 = (
    'Nair, R. R., Blake, P., et al. (2008). Fine Structure Constant Defines Visual Transparency of Graphene. '
    'Science 320(5881), 1308. | https://www.science.org/doi/10.1126/science.1156965'
)
COBRE = (
    'Langley Alloys. What is the thermal conductivity of copper? (valor de referencia: 401 W/m·K a 20 °C). | '
    'https://www.langleyalloys.com/knowledge-advice/what-is-the-thermal-conductivity-of-copper/'
)
GE_2022 = (
    'Ge et al. (2022). Graphene-Based Textiles for Thermal Management and Flame Retardancy. '
    'Advanced Functional Materials. | https://onlinelibrary.wiley.com/doi/full/10.1002/adfm.202205934'
)
JOULE = (
    'Graphene-functionalized textile composites for wearable Joule heating applications. ScienceDirect. | '
    'https://www.sciencedirect.com/science/article/pii/S2949944525000012'
)
LAVADO = (
    'Scalable fiber-skeleton-reinforced graphene-assembled films enabling wash-durable wearable heating. '
    'Nano Research. | https://www.sciopen.com/article/10.26599/NR.2026.94908671'
)
PENG_2025 = (
    'Peng, Y., Wang, D., Zheng, H., Qian, H., Chen, C., Han, Y., Zhao, K., Gao, T., Liu, W., Pang, X. (2025). '
    'Effects of Graphene-Based Far-Infrared Compression Garments on Aerobic Capacity in Healthy Young Males: '
    'A Randomized Crossover Trial. Sports Medicine - Open 11, 114. | '
    'https://pmc.ncbi.nlm.nih.gov/articles/PMC12514096/'
)
HUANG_2019 = (
    'Huang, H., Su, S., Wu, N., Wan, H., Wan, S., Bi, H., Sun, L. (2019). Graphene-Based Sensors for Human '
    'Health Monitoring. Frontiers in Chemistry. | https://pmc.ncbi.nlm.nih.gov/articles/PMC6580932/'
)
SENSOR_NYLON = (
    'Wearable graphene film strain sensors encapsulated with nylon fabric for human motion monitoring. '
    'Sensors and Actuators A. | https://www.sciencedirect.com/science/article/abs/pii/S0924424719302146'
)
SENSOR_ACSNANO = (
    'Graphene Textile Strain Sensor with Negative Resistance Variation for Human Motion Detection. ACS Nano. | '
    'https://pubs.acs.org/doi/10.1021/acsnano.8b03391'
)
AKHAVAN_2010 = (
    'Akhavan, O., Ghaderi, E. (2010). Toxicity of Graphene and Graphene Oxide Nanowalls Against Bacteria. '
    'ACS Nano 4, 5731-5736. doi:10.1021/nn101390x | https://doi.org/10.1021/nn101390x'
)
PNAS_2017 = (
    'Enhanced antibacterial activity through the controlled alignment of graphene oxide nanosheets. PNAS (2017). | '
    'https://www.pnas.org/doi/abs/10.1073/pnas.1710996114'
)
FLAGSHIP = (
    'Graphene Flagship. Understanding the health and safety of graphene. | '
    'https://graphene-flagship.eu/materials/news/understanding-the-health-and-safety-of-graphene'
)
SAFETY_2018 = (
    'Safety Assessment of Graphene-Based Materials: Focus on Human Health and the Environment. ACS Nano (2018). | '
    'https://pubs.acs.org/doi/10.1021/acsnano.8b04758'
)
CICLO_VIDA = (
    'Life-cycle risk assessment of graphene-enabled textiles in fire protection gear. ScienceDirect. | '
    'https://sciencedirect.com/science/article/pii/S2452074823000393'
)
ISO_20743 = (
    'ISO 20743:2021. Textiles - Determination of antibacterial activity of textile products. | '
    'https://www.iso.org/standard/79819.html'
)
PCM = (
    'An overview of phase change materials, their production, and applications in textiles. ScienceDirect. | '
    'https://www.sciencedirect.com/science/article/pii/S2590123024018462'
)
DEPORTE = (
    'Applications and development trends of textile materials in sports: A review. ScienceDirect. | '
    'https://www.sciencedirect.com/science/article/pii/S1110016825005903'
)


def _refs(*items):
    return '\n'.join(items)


POSTS = [
    {
        'slug': 'grafeno-el-material-de-un-solo-atomo-de-espesor',
        'title': 'Grafeno: el material de un solo átomo de espesor',
        'category': 'Materiales',
        'reading_time': 5,
        'excerpt': (
            'Una sola capa de átomos de carbono, aislada en 2004 y premiada con el Nobel en 2010, reúne '
            'propiedades que ninguna fibra convencional iguala. Esto es lo que se sabe y lo que no se debe '
            'prometer.'
        ),
        'content': '''En 2004, un equipo de la Universidad de Manchester encabezado por Andre Geim y Konstantin Novoselov publicó en Science cómo aislar y medir películas de carbono de un átomo de espesor [1]. Seis años después recibieron el Premio Nobel de Física "por sus experimentos pioneros sobre el material bidimensional grafeno" [2].

## Qué es, con precisión

La norma ISO/TS 80004-13 define el grafeno como una sola capa de átomos de carbono con hibridación sp² [3]. Cuando se apilan entre tres y diez capas se habla de grafeno de pocas capas [4], y cuando son muchas, de grafito, el mismo material de la mina de un lápiz.

Esta precisión importa fuera del laboratorio: en la práctica textil es habitual trabajar con derivados, como el óxido de grafeno o el óxido de grafeno reducido, cuyo comportamiento no es idéntico al de la lámina ideal [8].

## Cuatro propiedades que explican el interés

- **Resistencia.** En láminas suspendidas de una sola capa se midió un módulo de Young de 1,0 TPa y una resistencia intrínseca de 130 GPa [5].
- **Calor.** Su conductividad térmica a temperatura ambiente se midió entre 4.840 y 5.300 W/m·K [6], frente a unos 401 W/m·K del cobre [7].
- **Luz.** Una sola capa absorbe el 2,3 % de la luz blanca que le llega, un valor fijado por una constante fundamental de la física [9].
- **Electricidad.** Los primeros trabajos ya mostraron movilidades de electrones de unos 10.000 cm²/V·s a temperatura ambiente [1].

## De la lámina ideal a la prenda

Todas esas cifras corresponden a monocapas casi perfectas, medidas en condiciones de laboratorio. Una prenda no es eso. En un textil, el grafeno aparece como recubrimiento sobre la tela [10][11], como parte de una fibra compuesta [12] o como película laminada sobre un tejido [13], y el resultado final depende de cuánto material hay, en qué forma, y de qué tan bien se adhiere a la fibra después de usar y lavar la prenda.

Por eso el valor del grafeno para la ropa deportiva no está en una cifra récord, sino en las funciones concretas que se pueden medir en una prenda terminada: gestión del calor, conductividad para sensores, durabilidad. De cada una hablamos en las próximas entradas.

## Por qué lo seguimos de cerca

En GoToGym revisamos la ciencia de materiales para separar lo que está demostrado de lo que todavía es promesa. Lo que se afirme de una prenda concreta se indica en su ficha de producto; este artículo describe el estado de la ciencia, no las propiedades de un artículo en particular.''',
        'references': _refs(
            NOVOSELOV_2004, NOBEL_2010, ISO_80004, ISO_80004_2017, LEE_2008, BALANDIN_2008, COBRE,
            FLAGSHIP, NAIR_2008, GE_2022, JOULE, PENG_2025, SENSOR_NYLON,
        ),
    },
    {
        'slug': 'cuando-una-prenda-conduce-el-calor-grafeno-y-gestion-termica',
        'title': 'Cuando una prenda conduce el calor: grafeno y gestión térmica',
        'category': 'Tecnología textil',
        'reading_time': 5,
        'excerpt': (
            'El grafeno conduce el calor mejor que casi cualquier material conocido. Qué significa eso en una '
            'tela, qué se ha demostrado en prototipos y dónde están los límites.'
        ),
        'content': '''Entrenar es generar calor. Cómo lo maneja la ropa, si lo disipa, lo reparte o lo retiene, cambia la sensación de confort. Por eso la gestión térmica es el terreno donde más se investiga el grafeno en textiles.

## El punto de partida

En una monocapa suspendida de grafeno se midió una conductividad térmica de entre 4.840 y 5.300 W/m·K a temperatura ambiente [1], más de diez veces la del cobre, que ronda los 401 W/m·K [2]. De ahí la idea: una tela con grafeno podría repartir el calor del cuerpo de forma más uniforme.

## Dos maneras de usarlo

- **Pasiva: repartir calor.** El grafeno incorporado a la tela ayuda a extender el calor desde las zonas donde se acumula. Las revisiones sobre textiles de grafeno para gestión térmica y retardo de llama recogen esta línea de trabajo [3].
- **Activa: generar calor.** Como el grafeno conduce la electricidad y convierte la energía eléctrica en calor por efecto Joule, se han desarrollado telas recubiertas que funcionan como elementos calefactores flexibles para prendas con calefacción personalizada o uso terapéutico [4]. Requieren una fuente de energía, normalmente una batería pequeña.

## Lo que todavía es un desafío

- **Del laboratorio a la tela.** La cifra récord es de una lámina ideal. En un tejido, la conductividad efectiva depende de la cantidad de grafeno, de su forma y de cómo se conecta entre fibras.
- **Lavado.** Que el efecto sobreviva a decenas de lavados es un problema de investigación activa; hay trabajos centrados específicamente en calefactores textiles resistentes al lavado [5].
- **Confort.** Una prenda debe seguir siendo flexible, transpirable y suave. Un recubrimiento que mejora una métrica y empeora el tacto no sirve para entrenar.

## Cómo leer una afirmación térmica

Cuando una prenda promete "regular la temperatura", conviene preguntar qué se midió (conductividad, temperatura de piel, tiempo de secado), con qué método y después de cuántos lavados. Una promesa sin esas respuestas es publicidad, no ingeniería de producto.''',
        'references': _refs(BALANDIN_2008, COBRE, GE_2022, JOULE, LAVADO),
    },
    {
        'slug': 'corres-mas-con-grafeno-lo-que-dice-un-ensayo-en-humanos',
        'title': '¿Corres más con grafeno? Lo que dice (y lo que no) un ensayo en humanos',
        'category': 'Ciencia deportiva',
        'reading_time': 5,
        'excerpt': (
            'Una prueba con personas: un ensayo aleatorizado de doble ciego con prendas de '
            'compresión de grafeno. Resultados, límites y cómo interpretarlos con honestidad.'
        ),
        'content': '''Las afirmaciones sobre rendimiento son las que más se prestan al exceso. Por eso vale la pena mirar con detalle una prueba con personas reales.

## El estudio

En 2025, un equipo de investigación publicó en Sports Medicine - Open un ensayo aleatorizado, cruzado y de doble ciego [1]. Participaron 15 estudiantes universitarios varones, de 18 a 25 años, físicamente activos. Cada uno hizo dos pruebas incrementales en cinta, con siete días de separación: una con una camiseta y un pantalón de compresión fabricados con fibras compuestas de nailon y grafeno (emisividad infrarroja del 92 %), y otra con prendas idénticas sin grafeno.

## Lo que encontraron

- **Duración del esfuerzo.** 791,9 s con grafeno frente a 753,5 s con la prenda de control: 38,4 s más, es decir, alrededor de un 5 %.
- **Frecuencia cardíaca máxima.** Ligeramente menor con grafeno (198,8 frente a 200,3 latidos por minuto).
- **Consumo máximo de oxígeno (VO₂máx).** Sin diferencia significativa entre ambas condiciones.

Los autores concluyen que las prendas mejoraron la capacidad aeróbica y reducieron la carga cardíaca [1].

## Lo que no dice

- **Es un solo estudio, pequeño.** Quince personas, todas varones y recreativamente activos. Los propios autores señalan el tamaño reducido de la muestra.
- **No se midió el mecanismo.** El trabajo atribuye el efecto a la emisión de infrarrojo lejano, pero no registró temperatura de piel ni temperatura central, ni flujo sanguíneo, ni la presión real de la compresión.
- **No se comprobó el cegamiento.** No se evaluó si los participantes podían adivinar qué prenda llevaban.

## Cómo lo leemos

Es un resultado prometedor y una hipótesis que merece replicarse con más personas, con mujeres y con deportistas de distinto nivel, midiendo el mecanismo. No es una garantía de que una prenda "te haga rendir más". Preferimos decir exactamente eso, y esperar a que la evidencia crezca antes de convertirla en una promesa.''',
        'references': _refs(PENG_2025),
    },
    {
        'slug': 'prendas-que-sienten-sensores-textiles-de-grafeno',
        'title': 'Prendas que sienten: sensores textiles de grafeno',
        'category': 'Tecnología textil',
        'reading_time': 4,
        'excerpt': (
            'Movimiento articular y señales del cuerpo: el grafeno permite integrar sensores finos y flexibles '
            'en la propia tela. Qué se ha logrado y qué falta para que salga del laboratorio.'
        ),
        'content': '''Un sensor tradicional se lleva puesto. Un sensor textil es parte de la prenda. El grafeno, por su espesor atómico y su conductividad, es uno de los materiales más estudiados para lograrlo.

## Qué puede medir

Las revisiones de sensores de grafeno para monitoreo de salud describen aplicaciones no invasivas y portátiles [1]. En textiles, los prototipos publicados se han probado en la detección del movimiento humano, como el de las articulaciones [2][3].

Algunas cifras de la literatura, que dependen mucho del diseño de cada sensor [1]:

- Sensores de presión con sensibilidades entre 0,82 y 25,1 kPa⁻¹.
- Sensores de deformación con factores de galga entre 25,2 y 502.
- Electrodos flexibles que admiten más de un 40 % de estiramiento.

## Por qué el grafeno

La revisión señala que su alta superficie específica y su espesor atómico explican la sensibilidad, y que su flexibilidad y delgadez permiten un contacto íntimo y conforme con la piel [1]. En el ámbito deportivo, esto abre la puerta a analizar la técnica de movimiento sin cables ni dispositivos aparte.

## Lo que falta

- **Durabilidad.** Los mismos autores identifican la longevidad del sensor como un problema pendiente [1].
- **Biocompatibilidad.** Siguen existiendo debates por la gran heterogeneidad de los materiales basados en grafeno, y faltan datos sobre efectos de acumulación a largo plazo [1].
- **Del prototipo al producto.** Alimentación, electrónica, lavado y calibración son retos de ingeniería tan importantes como el material.

## Qué esperar

Es un campo con avances reales y publicados, pero mayoritariamente en fase de prototipo. Una prenda con sensores de grafeno listos para uso cotidiano exige resolver esos puntos, no solo contar con un material sensible. Cuando lo hagamos, lo diremos con datos.''',
        'references': _refs(HUANG_2019, SENSOR_NYLON, SENSOR_ACSNANO),
    },
    {
        'slug': 'antibacteriano-y-seguro-separar-evidencia-y-marketing-en-el-grafeno',
        'title': 'Antibacteriano y seguro: separar evidencia y marketing en el grafeno',
        'category': 'Materiales',
        'reading_time': 6,
        'excerpt': (
            'El grafeno daña bacterias en el laboratorio, pero eso no equivale a una prenda antibacteriana. '
            'Qué dice la ciencia sobre actividad antimicrobiana y sobre seguridad, y cómo leer una etiqueta.'
        ),
        'content': '''"Antibacteriano" es una de las palabras más usadas en la ropa deportiva. Con el grafeno aparece a menudo, y conviene entender de dónde viene y hasta dónde llega.

## Qué se demostró

Un trabajo de 2010 en ACS Nano estudió la toxicidad de láminas de grafeno y de óxido de grafeno frente a bacterias y encontró que estos materiales eran dañinos para ellas [1]. Ese trabajo, muy citado, alimentó las investigaciones posteriores sobre textiles con actividad antibacteriana.

## Por qué no basta

- **Es un ensayo de laboratorio.** Se hizo con láminas y películas de grafeno preparadas para el experimento, no con una prenda usada y lavada.
- **La forma importa.** Otro estudio muestra que la actividad antibacteriana del óxido de grafeno puede cambiar según cómo se alineen sus láminas [2].
- **El grafeno no es uno solo.** Su comportamiento biológico depende del estado de oxidación, del tamaño de las láminas y de cómo se preparó [3].

La conclusión honesta es que hay una base científica para investigar la función antibacteriana, no una garantía automática para cualquier prenda "con grafeno".

## Seguridad: qué se sabe

El programa europeo de investigación Graphene Flagship resume que el grafeno y los materiales en capas son en general seguros si se manejan adecuadamente, y que la seguridad depende de las propiedades concretas del material y de las condiciones de exposición [3]. Entre sus hallazgos:

- En la piel, solo concentraciones altas con exposiciones largas produjeron daño de membrana; la toxicidad cutánea resulta baja.
- En pulmones, las partículas nanométricas de óxido de grafeno se mostraron seguras, mientras que las más grandes pueden causar efectos adversos.
- Para trabajadores expuestos de forma crónica no se observó una respuesta inmune significativa.

Un análisis del ciclo de vida de textiles con grafeno para equipos de protección contra incendios ubicó los mayores riesgos de exposición en la manufactura, por inhalación, y no en el uso, porque una vez integrado en el producto es muy difícil que se liberen partículas [4]. Es un recordatorio de que la seguridad también es responsabilidad de quien fabrica. Hay revisiones más amplias sobre salud y ambiente [5].

## Cómo leer una etiqueta

Ante una prenda que diga "antibacteriana" o "con grafeno", conviene preguntar:

- ¿Qué forma de grafeno contiene (monocapa, pocas capas, óxido) y en qué proporción?
- ¿Con qué método se midió la actividad antibacteriana? Existe una norma específica para textiles, la ISO 20743 [6].
- ¿Se midió después de lavar la prenda y cuántas veces?

Si no hay respuestas, la palabra es solo una palabra.''',
        'references': _refs(AKHAVAN_2010, PNAS_2017, FLAGSHIP, CICLO_VIDA, SAFETY_2018, ISO_20743),
    },
    {
        'slug': 'ropa-deportiva-funcionalizada-como-se-disena-la-respuesta-de-una-tela',
        'title': 'Ropa deportiva funcionalizada: cómo se diseña la respuesta de una tela',
        'category': 'Tecnología textil',
        'reading_time': 5,
        'excerpt': (
            'Humedad, temperatura, sensado: una tela "funcional" es la suma de fibras, estructura y acabados. '
            'Un mapa de las estrategias y de dónde encaja el grafeno.'
        ),
        'content': '''Funcionalizar un textil es darle una función que la fibra por sí sola no tiene. Se logra en distintos niveles: dentro de la fibra, en el hilo, en la estructura del tejido o con un acabado sobre la tela. Cada nivel tiene ventajas y costos.

## Tres funciones que importan al entrenar

- **Gestión de la humedad.** La estrategia es la capilaridad: canales microscópicos entre las fibras que llevan el sudor lejos de la piel hacia la superficie de la tela, donde se evapora.
- **Gestión térmica.** Además de la conductividad de las fibras y la porosidad de la tela, se usan materiales de cambio de fase (PCM) que absorben o liberan calor latente en un rango estrecho de temperatura. Su limitación conocida es la baja conductividad térmica y el riesgo de fugas [2].
- **Sensado y conductividad.** Aquí entran los materiales conductores, entre ellos el grafeno, para medir movimiento o generar calor.

## Dónde encaja el grafeno

No reemplaza a las otras estrategias, las complementa. Los trabajos sobre textiles con grafeno para gestión térmica [3] y las revisiones sobre materiales textiles en el deporte [1] muestran un panorama de combinaciones, no de una solución única.

## Principios para diseñar una prenda funcional

- **Una función, una métrica.** Si se promete secado rápido, debe medirse el secado; si se promete regular el calor, la temperatura o la conductividad.
- **Durabilidad como requisito.** Una función que desaparece en cinco lavados no es una función.
- **Confort primero.** Tacto, elasticidad y respirabilidad no se negocian.
- **Evidencia proporcional.** Un resultado de laboratorio se comunica como resultado de laboratorio.

## Lo que viene

La tendencia es combinar funciones en una misma prenda y validarlas con pruebas en humanos, no solo en laboratorio. Es el estándar con el que queremos mirar cada material nuevo.''',
        'references': _refs(DEPORTE, PCM, GE_2022),
    },
]
