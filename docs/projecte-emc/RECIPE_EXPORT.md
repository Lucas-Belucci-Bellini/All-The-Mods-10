# Exportação de receitas para JSON

Este procedimento cria um catálogo legível por ferramentas de análise/IA com as receitas que o KubeJS consegue ver durante o carregamento de receitas da instância ATM10.

## Arquivos

- Script exportador: [`kubejs/server_scripts/zzzz_export_recipe_catalog.js`](../../kubejs/server_scripts/zzzz_export_recipe_catalog.js)
- Saída gerada localmente: `kubejs/recipe_catalog_export.json`
- Contrato do JSON: [`recipe-catalog.schema.json`](recipe-catalog.schema.json)

## Como gerar na instância local

1. Obtenha a branch `work/projecte-emc-balancing` na pasta que corresponde à instância que você está testando, ou copie o script exportador para `kubejs/server_scripts/zzzz_export_recipe_catalog.js`.
2. Inicie o modpack ou, se o script já estiver instalado e o mundo estiver aberto, execute `/reload`. O evento `ServerEvents.recipes` é disparado no carregamento/recarregamento das receitas.
3. Confira `logs/latest.log` (ou o console) pela mensagem `[RecipeCatalogExport] Wrote N recipes to kubejs/recipe_catalog_export.json`.
4. Verifique o arquivo `kubejs/recipe_catalog_export.json`. Ele contém os dados de cada receita, ID, tipo, fonte e resumos por tipo/namespace.
5. Para colocar o resultado real no GitHub, adicione o arquivo gerado ao commit na branch de trabalho depois de conferir seu tamanho e conteúdo. O exportador em si não publica automaticamente no GitHub.

## Formato do catálogo

O catálogo contém:
- `schemaVersion`: versão do contrato do JSON.
- `generatedAt`, `gameVersion`, `modLoader`: metadados da execução.
- `coverage`: limites conhecidos da exportação.
- `summary`: total de receitas, itens ignorados por erro de serialização e contagens por tipo/namespace.
- `recipes[]`: `id`, `type`, `source` e `data` com o JSON da receita.

A lista é ordenada por ID para reduzir diferenças desnecessárias entre exportações.

## Limites importantes

A lista só deve ser tratada como completa para as receitas que estão visíveis ao evento do KubeJS nesta combinação exata de mods e configurações. Ela pode incluir receitas de JSON carregadas por datapacks/mods e as receitas do KubeJS que já foram registradas antes da execução do exportador.

Alguns mods executam lógica de máquinas diretamente em Java ou registram receitas de formas que não têm uma representação JSON acessível ao KubeJS. Essas receitas precisam de um processo complementar; o exportador informa explicitamente que não pode garanti-las.

O script é somente leitura: não cria, remove ou modifica receitas de jogo. Ele grava apenas o arquivo de catálogo. O resultado não deve ser usado como prova de equilíbrio de EMC sem uma auditoria dos ingredientes, saídas, quantidades, chances, fluidos, energia, subprodutos e máquinas.

## Atualização futura

Depois de atualizar mods, scripts ou datapacks, rode `/reload` novamente e gere um novo catálogo. Ao comparar dois catálogos, use `recipes[].id` como chave e observe mudanças em `type` e `data`.
