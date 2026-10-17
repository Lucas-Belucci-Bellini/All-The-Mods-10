// Exporta o catálogo de receitas visível no evento do KubeJS.
// Este script é somente leitura: não adiciona, remove nem altera receitas.
// O nome zzzz ajuda a executar depois dos outros scripts, que no KubeJS 7.2+
// são carregados em ordem alfabética, sem diferenciar maiúsculas/minúsculas.
//
// Saída: kubejs/recipe_catalog_export.json
// Para regenerar, use /reload depois que este arquivo estiver na instância.

ServerEvents.recipes(event => {
  const entriesById = new Map();
  let skippedRecipes = 0;
  let removedRecipes = 0;

  const addRecipeToCatalog = (recipe, fallbackSource) => {
    if (!recipe) {
      return;
    }

    if (recipe.removed) {
      removedRecipes++;
      return;
    }

    try {
      // getOrCreateId() is intentionally hidden from KubeJS scripts in
      // this version. getId() is public and safely creates an ID when needed.
      const id = recipe.id != null
        ? recipe.id.toString()
        : recipe.getId();

      // KubeJS exposes its current recipe JSON as a Gson JsonObject.
      // Converting through its JSON text produces a plain serializable object.
      const data = JSON.parse(recipe.json.toString());
      const type = typeof data.type === 'string' ? data.type : 'unknown';

      let source = fallbackSource;
      if (recipe.newRecipe) {
        source = 'kubejs_added';
      } else if (recipe.hasChanged()) {
        source = 'modified_original';
      }

      // Map deduplicates IDs. Added KubeJS recipes are processed after originals
      // so that a same-ID KubeJS replacement wins in this export.
      entriesById.set(id, {
        id,
        type,
        source,
        data
      });
    } catch (error) {
      skippedRecipes++;
      console.error('[RecipeCatalogExport] Could not export a recipe: ' + error);
    }
  };

  // The original map includes recipes loaded from datapack/mod recipe JSON.
  event.originalRecipes.values().forEach(recipe => {
    addRecipeToCatalog(recipe, 'loaded_recipe_json');
  });

  // Include recipes registered by KubeJS scripts that have already run.
  event.addedRecipes.forEach(recipe => {
    addRecipeToCatalog(recipe, 'kubejs_added');
  });

  const recipes = Array.from(entriesById.values()).sort((a, b) =>
    a.id.localeCompare(b.id)
  );

  const byType = {};
  const byNamespace = {};

  recipes.forEach(recipe => {
    byType[recipe.type] = (byType[recipe.type] || 0) + 1;

    const namespace = recipe.id.includes(':')
      ? recipe.id.substring(0, recipe.id.indexOf(':'))
      : 'minecraft';

    byNamespace[namespace] = (byNamespace[namespace] || 0) + 1;
  });

  const catalog = {
    schemaVersion: '1.0.0',
    status: 'generated',
    generatedAt: new Date().toISOString(),
    gameVersion: '1.21.1',
    modLoader: 'NeoForge',
    exportMethod: 'KubeJS ServerEvents.recipes',
    coverage: {
      includesLoadedRecipeJson: true,
      includesKubeJSRecipesAlreadyRegisteredAtExportTime: true,
      includesRecipesRemovedByPackScripts: false,
      guaranteesJavaCodeOnlyRecipes: false,
      note: 'This catalog covers recipes visible to KubeJS during its recipe event. Some code-only machine behaviors may not have JSON representations and need separate inspection.'
    },
    summary: {
      totalRecipes: recipes.length,
      skippedBecauseOfSerializationErrors: skippedRecipes,
      removedRecipesEncountered: removedRecipes,
      byType,
      byNamespace
    },
    recipes
  };

  try {
    JsonIO.write('kubejs/recipe_catalog_export.json', catalog);
    console.info(
      '[RecipeCatalogExport] Wrote ' + recipes.length +
      ' recipes to kubejs/recipe_catalog_export.json; skipped=' +
      skippedRecipes + ', removed=' + removedRecipes
    );
  } catch (error) {
    console.error('[RecipeCatalogExport] Failed to write catalog: ' + error);
  }
});
