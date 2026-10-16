# Errors detected
- [`Invalid component ingredients: ingredient[]`](#invalid-component-ingredients-ingredient)
- [`Invalid component key: pattern<ingredient>`](#invalid-component-key-patterningredient)

##### `Invalid component ingredients: ingredient[]`

<details>
<summary>herbsandharvest:pepperoni</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/herbsandharvest`

```json
{
  "type": "minecraft:crafting_shapeless",
  "category": "misc",
  "ingredients": [
    {
      "tag": "c:foods/beef"
    },
    {
      "tag": "c:foods/pork"
    },
    {
      "tag": "c:foods/minced_garlic"
    },
    {
      "tag": "c:items/pepper"
    },
    {
      "item": "herbsandharvest:mustard_seeds"
    }
  ],
  "result": {
    "count": 1,
    "id": "herbsandharvest:pepperoni"
  }
}
```

</details>

<details>
<summary>herbsandharvest:sausage</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/herbsandharvest`

```json
{
  "type": "minecraft:crafting_shapeless",
  "category": "misc",
  "ingredients": [
    {
      "tag": "c:foods/pork"
    },
    {
      "tag": "c:foods/minced_garlic"
    },
    {
      "item": "herbsandharvest:chopped_sage"
    },
    {
      "item": "herbsandharvest:chopped_thyme"
    },
    {
      "item": "herbsandharvest:chopped_rosemary"
    },
    {
      "tag": "c:items/salt"
    },
    {
      "tag": "c:items/pepper"
    }
  ],
  "result": {
    "count": 1,
    "id": "herbsandharvest:sausage"
  }
}
```

</details>

##### `Invalid component key: pattern<ingredient>`

<details>
<summary>ae2extras:network/cells/chemical_cell_16m</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/ae2extras`

```json
{
  "type": "minecraft:crafting_shaped",
  "category": "redstone",
  "key": {
    "a": {
      "item": "ae2:quartz_glass"
    },
    "b": {
      "tag": "c:dusts/redstone"
    },
    "c": {
      "item": "ae2extras:cell_component_16m"
    },
    "d": {
      "tag": "ae2extras:ingots/osmium"
    }
  },
  "pattern": [
    "aba",
    "bcb",
    "ddd"
  ],
  "result": {
    "count": 1,
    "id": "ae2extras:chemical_cell_16m"
  }
}
```

</details>

<details>
<summary>ae2extras:network/cells/chemical_cell_1m</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/ae2extras`

```json
{
  "type": "minecraft:crafting_shaped",
  "category": "redstone",
  "key": {
    "a": {
      "item": "ae2:quartz_glass"
    },
    "b": {
      "tag": "c:dusts/redstone"
    },
    "c": {
      "item": "ae2extras:cell_component_1m"
    },
    "d": {
      "tag": "ae2extras:ingots/osmium"
    }
  },
  "pattern": [
    "aba",
    "bcb",
    "ddd"
  ],
  "result": {
    "count": 1,
    "id": "ae2extras:chemical_cell_1m"
  }
}
```

</details>

<details>
<summary>ae2extras:network/cells/chemical_cell_4m</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/ae2extras`

```json
{
  "type": "minecraft:crafting_shaped",
  "category": "redstone",
  "key": {
    "a": {
      "item": "ae2:quartz_glass"
    },
    "b": {
      "tag": "c:dusts/redstone"
    },
    "c": {
      "item": "ae2extras:cell_component_4m"
    },
    "d": {
      "tag": "ae2extras:ingots/osmium"
    }
  },
  "pattern": [
    "aba",
    "bcb",
    "ddd"
  ],
  "result": {
    "count": 1,
    "id": "ae2extras:chemical_cell_4m"
  }
}
```

</details>

<details>
<summary>ae2extras:network/cells/chemical_cell_64m</summary>

`Component 'ingredient' is not allowed to be empty!`

`mod/ae2extras`

```json
{
  "type": "minecraft:crafting_shaped",
  "category": "redstone",
  "key": {
    "a": {
      "item": "ae2:quartz_glass"
    },
    "b": {
      "tag": "c:dusts/redstone"
    },
    "c": {
      "item": "ae2extras:cell_component_64m"
    },
    "d": {
      "tag": "ae2extras:ingots/osmium"
    }
  },
  "pattern": [
    "aba",
    "bcb",
    "ddd"
  ],
  "result": {
    "count": 1,
    "id": "ae2extras:chemical_cell_64m"
  }
}
```

</details>

