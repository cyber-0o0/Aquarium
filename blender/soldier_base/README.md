# Soldier base body (RTS)

Стилизованный базовый пехотинец для top-down RTS, построенный процедурно в Blender 4.2.

- T-поза, руки горизонтально, ладони вниз (большие пальцы вперёд), ноги прямые, стопы на ширине плеч.
- Рост 1.8 м, Z вверх, лицом в −Y (вид Front в Blender), начало координат между стопами.
- Однотонная полевая форма олива (китель заправлен, ремень, карго-брюки), ботинки, перчатки.
  Без шлема, жилета, рюкзака, оружия и подсумков: чистая база под модульное снаряжение.
- Слегка стилизованные пропорции: кисти и ботинки немного увеличены, голова на 7% крупнее.

## Файлы

| Файл | Что это |
|---|---|
| `soldier_base.blend` | Исходник: процедурные hand-painted материалы, риг, рендер-сцена |
| `soldier_base_game.blend` | То же с запечёнными BaseColor-текстурами (по одному материалу на часть) |
| `soldier_base.glb` / `.fbx` | Экспорт со скином и текстурами (≈52k треугольников) |
| `soldier_base_lod1.glb` | Децимированный LOD (≈30% полигонов) |
| `textures/` | Запечённый альбедо, без света и теней |
| `soldier_base_turnaround.png` | Лист front / side / back (орто, ровный свет, светло-серый фон) |
| `renders/` | Отдельные виды + 3/4 и вид RTS-камеры сверху |
| `build_soldier.py` | Скрипт, который собирает всё это с нуля |

Меши: `Soldier_Body`, `Soldier_Hair`, `Soldier_Gloves`, `Soldier_Boots`. Все привязаны к `Armature`
(Root, Hips, Spine, Chest, Neck, Head, Shoulder/UpperArm/LowerArm/Hand, по 2 кости на палец,
UpperLeg/LowerLeg/Foot/Toes; суффиксы `.L` / `.R`). Веса плавно распределены по расстоянию до костей.

## Пересборка

```bash
pip install bpy==4.2.0 pillow "numpy<2"
python3 build_soldier.py            # всё: .blend, рендеры, бейк, GLB/FBX (~3 мин на CPU)
python3 build_soldier.py --preview  # быстрый тёрнэраунд + крупные планы
# или: blender -b -P build_soldier.py -- --preview
```

Пропорции, цвета и детали заданы числами в начале каждого блока скрипта (HEAD, JACKET, GLOVES,
TROUSERS, BOOTS).
