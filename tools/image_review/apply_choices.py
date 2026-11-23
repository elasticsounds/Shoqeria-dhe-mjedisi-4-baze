#!/usr/bin/env python3
"""Applies the picture choices of 2026-11-23 from choices.json to the specs, images/ and the alt texts.
Run with: uv run --with pillow python3 tools/image_review/apply_choices.py ; then python3 tools/build_lessons.py"""
import glob, json, os
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
G = 'tools/image_review/generated/'
# old src in the specs -> (source file, new file or None to use the source as is)
SWAP = {
 'images/pg009_im001_pdf.png': (G+'pg009_im001_pdf_20261122_123819.png', 'images/pg009_im001_inclusive.png'),
 'images/pg011_im001_pdf.png': (G+'pg011_im001_pdf_20261122_124038.png', 'images/pg011_im001_inclusive.png'),
 'images/pg011_im002_pdf.png': (G+'pg011_im002_pdf_20261122_124658.png', 'images/pg011_im002_inclusive.png'),
 'images/pg012_im001_crop_v1.png': (G+'p012_1_20261122_124656.png', 'images/pg012_im001_inclusive.png'),
 'images/pg015_im001.png': (G+'pg015_im001_20261122_124657.png', 'images/pg015_im001_inclusive.png'),
 'images/pg021_fig1_pdf.png': (G+'p021_1_20261122_124702.png', 'images/pg021_im001_inclusive.png'),
 'images/pg033_fig1_pdf.png': ('images/pg033_im002.png', None),
 'images/pg042_im001_crop.png': (G+'p042_1_20261122_124707.png', 'images/pg042_im001_inclusive.png'),
 'images/pg043_im001_crop.png': (G+'p043_1_20261122_124706.png', 'images/pg043_im001_inclusive.png'),
 'images/pg044_im002.png': ('studio/assets/pg044_sec001-composite.png', None),
 'images/pg051_im001_crop.png': (G+'p051_1_20261122_124716.png', 'images/pg051_im001_inclusive.png'),
 'images/pg053_im001_crop_v1.png': (G+'p053_1_20261122_124717.png', 'images/pg053_im001_inclusive.png'),
 'images/pg055_fig1_pdf.png': ('images/pg055_im001.png', None),
 'images/pg057_fig1_pdf.png': ('studio/assets/pg057_sec001-scene.png', None),
 'images/pg058_im001_seg001_v1.png': (G+'p058_1_20261122_124720.png', 'images/pg058_im001_seg001_inclusive.png'),
 'images/pg058_im001_seg002_v1.png': (G+'p058_2_20261122_124722.png', 'images/pg058_im001_seg002_inclusive.png'),
 'images/pg058_im001_seg003_v1_crop_v1.png': (G+'p058_3_20261122_124721.png', 'images/pg058_im001_seg003_inclusive.png'),
 'images/pg059_im001_seg003_v1.png': ('studio/assets/pg059_sec001-notary.png', 'images/pg059_notary_flamur.png'),
 'images/pg059_im001_seg004_v1.png': ('studio/assets/pg059_sec001-lawyer.png', 'images/pg059_lawyer_flamur.png'),
 'images/pg059_im001_seg002_v1.png': ('studio/assets/pg059_sec001-prosecutor.png', 'images/pg059_prosecutor_flamur.png'),
 'images/pg059_im001_seg001_v1.png': ('studio/assets/pg059_sec001-judge.png', 'images/pg059_judge_flamur.png'),
 'images/pg063_map_pdf.png': ('studio/assets/pg063_sec001-map.png', None),
 'images/pg066_map_pdf.png': ('studio/assets/pg066_sec001-map.png', 'images/pg066_map_flamur.png'),
 'images/pg067_scene.png': (G+'p067_1_20261122_124816.png', 'images/pg067_scene_inclusive.png'),
 'studio/assets/pg118_sec001-bus.png': (G+'p118_1_20261122_124736.png', 'images/pg118_bus_inclusive.png'),
}
TEXTS = {
 'pg009_im001': 'Një shtëpi e madhe rozë me banorë në dritare dhe ballkone, ndërsa në rrugë fëmijët përqafohen, shëtisin qenin dhe ngasin së bashku një biçikletë; mes tyre janë dy fëmijë në karrocë me rrota, një djalë i verbër me qen udhërrëfyes dhe një vajzë me shkop të bardhë.',
 'pg011_im001': 'Tre fëmijë vallëzojnë të lumtur së bashku, me duart lart dhe nota muzikore përreth; njëra prej tyre vallëzon e ulur në karrocë me rrota.',
 'pg011_im002': 'Një djalë dhe një vajzë me veshje sportive luajnë futboll së bashku para portës.',
 'pg012_im001_crop_v1': 'Dy nxënëse në korridorin e shkollës po sjellin kuti me dhurata; njëra prej tyre lëviz me karrocë me rrota dhe e mban kutinë në prehër. Pako të tjera janë mbledhur për t’u dhuruar fëmijëve në nevojë.',
 'pg015_im001': 'Mësuesja para tabelës u flet nxënësve në klasë, ndërsa ata janë ulur në banka dhe e dëgjojnë; njëri nga nxënësit është ulur në karrocë me rrota.',
 'pg021_im001_crop_v1': 'Mjekja me mantel të bardhë po u flet disa fëmijëve në një qendër shëndetësore; njëri nga fëmijët është në karrocë me rrota.',
 'pg033_fig1': 'Familje e ulur bashkë në divan në shtëpi gjatë pandemisë, duke menduar me shqetësim për koronavirusin; njëri nga djemtë është ulur në karrocë me rrota, ndërsa pranë tyre janë një mace, një qen dhe bimë.',
 'pg042_im001': 'Pesë fëmijë të ulur rreth një tavoline po diskutojnë për organizimin e një aktiviteti, me ide për mbledhjen e lodrave, rrobave dhe librave; njëri prej tyre mban aparat dëgjimi dhe një vajzë është ulur në karrocë me rrota.',
 'pg043_im001': 'Gjashtë fëmijë qëndrojnë së bashku në grup, duke paraqitur bashkëpunim, përfshirje dhe respekt mes njëri-tjetrit; njëri është në karrocë me rrota dhe një tjetër mban shkop të bardhë.',
 'pg044_im002': 'Mësuesja qëndron mes dy nxënësve në banka dhe i nxit të shprehin mendime të ndryshme; mbi secilin nxënës është një flluskë mendimi me një fotografi.',
 'pg051_im001_crop_v1': 'Familja e ulur rreth tavolinës diskuton së bashku dhe ndan mendime për të marrë një vendim; njëra nga gratë është ulur në karrocë me rrota.',
 'pg053_im001_crop_v1': 'Dy nxënës bisedojnë me dy të rritur për të gjetur një zgjidhje të përbashkët për një problem në shkollë; njëri nga nxënësit qëndron në këmbë me paterica.',
 'pg058_im001_seg001_v1': 'Katër nxënës diskutojnë rreth një tavoline, duke shprehur mendimet e tyre dhe duke krahasuar idetë me njëri-tjetrin; njëra nxënëse është ulur në karrocë me rrota.',
 'pg058_im001_seg002_v1': 'Një nxënëse shpjegon mendimin e saj para shokëve, ndërsa ata e dëgjojnë gjatë diskutimit; njëra prej tyre është ulur në karrocë me rrota dhe një djalë mban aparat dëgjimi.',
 'pg058_im001_seg003_v1_crop_v1': 'Katër nxënës bisedojnë; njëri, që ka një këmbë protezë, ka ngritur dorën për të folur, ndërsa të tjerët e dëgjojnë me kujdes.',
 'pg063_im004': 'Harta e Kosovës e ndarë në dy rajone: Rrafshi i Dukagjinit me ngjyrë të verdhë dhe Fusha e Kosovës me ngjyrë të gjelbër, me qendrat rajonale Peja, Gjakova, Prizreni, Mitrovica, Prishtina, Gjilani dhe Ferizaj.',
 'pg067_im001_crop_v1': 'Shoferi pranë veturës i dorëzon pasaportën policës në vendkalimin kufitar.',
 'pg118_im001': 'Autobus i verdhë i transportit publik me rampë të ulur te dera; një person në karrocë me rrota po hipën në autobus. Në sfond janë ndërtesat e qytetit.',
 'pg070_im005': 'Diagram i Venit: dy rrathë të zbrazët që priten në mes.',
}

def flat(im):
    im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im); return bg.convert('RGB')

for old, (src, new) in SWAP.items():
    if not new:
        continue
    im = Image.open(src)
    if 'pg059' in new:                     # thin yellow frame lines at the edges
        im = flat(im); im = im.crop((4, 4, im.width - 4, im.height - 4))
    elif 'pg066' in new:                   # printed page number "66 |" at the bottom left
        im = flat(im); im.paste('white', (60, 1350, 260, im.height))
    elif im.width > 1280:
        im = im.resize((1280, round(im.height * 1280 / im.width)), Image.LANCZOS)
    im.save(new, optimize=True)

specs = {p: open(p, encoding='utf-8').read() for p in glob.glob('tools/specs/*.json')}
for old, (src, new) in SWAP.items():
    hits = [p for p, s in specs.items() if f'"{old}"' in s]
    assert len(hits) == 1 and specs[hits[0]].count(f'"{old}"') == 1, (old, hits)
    specs[hits[0]] = specs[hits[0]].replace(f'"{old}"', f'"{new or src}"')
for p, s in specs.items():
    open(p, 'w', encoding='utf-8').write(s)

# page 70: Flamur's empty Venn diagram above the writing task
p = 'tools/specs/special.json'
spec = json.load(open(p, encoding='utf-8'))
scr = next(s for s in spec['screens'] if s['id'] == 'pg070_sec001')
if not any(b.get('figures', [{}])[0].get('id') == 'pg070_im005' for b in scr['blocks'] if b['type'] == 'gallery'):
    i = next(i for i, b in enumerate(scr['blocks']) if b['type'] == 'write')
    scr['blocks'].insert(i, {'type': 'gallery', 'figures': [{'src': 'images/pg070_im005.png', 'id': 'pg070_im005'}]})
json.dump(spec, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

for name in ('texts.json', 'speech_texts.json'):
    path = 'content/i18n/sq-XK/' + name
    d = json.load(open(path, encoding='utf-8'))
    missing = [k for k in TEXTS if k not in d and k != 'pg070_im005']
    d.update(TEXTS)
    json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(name, 'updated; ids that were new:', missing)
