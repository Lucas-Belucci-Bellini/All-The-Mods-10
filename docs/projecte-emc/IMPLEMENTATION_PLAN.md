# ProjectE EMC do zero — plano canônico

**Branch de trabalho:** `work/projecte-emc-balancing`  
**Objetivo:** ter EMC funcional e balanceado no ATM10 sem depender de AutoEMC ou ProjectE Integration.

## Princípio fundamental

O ProjectE já possui mapeadores nativos para valores conhecidos e para receitas que reconhece. **Não vamos reimplementar em outra ferramenta os cálculos normais que o próprio ProjectE faz.** Nossa ferramenta externa deve organizar dados, controlar exceções, validar arquivos e encontrar lacunas; não deve atribuir valores arbitrários a todos os itens.

## Dependências e fronteiras

- Manter ProjectE como motor de EMC e de transmutação.
- Manter Project Expansion enquanto não houver evidência de que ele é a causa do problema.
- A solução nova não usa AutoEMC nem ProjectE Integration.
- O valor final de um item deve vir de uma destas fontes identificáveis: mapeador nativo do ProjectE, override aprovado na nossa política ou conversão personalizada revisada.
- Não declarar o sistema pronto só porque a janela do jogo abriu: testar o carregamento dos mapeamentos e o comportamento no mundo.

## Dados de entrada e saída

### 1. Catálogo de receitas

O exportador KubeJS em `kubejs/server_scripts/zzzz_export_recipe_catalog.js` foi criado para gravar `kubejs/recipe_catalog_export.json` com os JSONs de receitas visíveis ao evento. É um inventário de análise; não altera receitas e não é uma promessa de que todos os comportamentos internos de máquinas estão representados.

Antes de usar um catálogo numa decisão de EMC, conferir `summary.totalRecipes`, `summary.skippedBecauseOfSerializationErrors`, fontes e tipos. Receitas de máquinas implementadas apenas em Java, receitas condicionais e outros comportamentos sem JSON acessível precisam de auditoria separada.

### 2. Política manual

A fonte de verdade dos overrides aprovados será `docs/projecte-emc/emc-policy.json`.

- Cada entrada manual precisa de um ID ou uma tag, um EMC inteiro não negativo, um estado (`draft` ou `approved`) e uma justificativa.
- Apenas entradas `approved` são exportadas para uso.
- Uma tag só deve ser usada quando a regra de economia se aplica de modo consistente a todos os itens abrangidos.
- Nunca aceitar como aprovados valores derivados de uma tabela antiga sem passar pela auditoria.

### 3. Arquivo consumido pelo ProjectE

O formato de `config/ProjectE/custom_emc.json` é o formato nativo do ProjectE: `comment` opcional e `entries` em array, com objetos contendo `id` ou `tag` e `emc`. A ferramenta em `tools/projecte-emc/build_custom_emc.py` cria uma saída candidata em `build/projecte-emc/custom_emc.json`; **ela não sobrescreve a configuração ativa automaticamente**. A saída deve ser revisada e testada antes de ser copiada para a instância.

## Plano de execução

### Fase 0 — ponto de partida seguro

- [x] Criar branch de trabalho, separada de `main`.
- [x] Confirmar que ProjectE e Project Expansion permanecem instalados na configuração atual do repositório, e que os JARs de AutoEMC e ProjectE Integration não estão na pasta `mods/`.
- [x] Registrar a tabela antiga de custom EMC como arquivo legado separado, sem usá-la na configuração ativa.
- [ ] Confirmar em runtime que o ProjectE inicia sem os dois addons e que a tabela de transmutação funciona.
- [ ] Preservar o mundo fora do fluxo de atualização da branch; siga o README antes de atualizar a instância.

### Fase 1 — comprovar o mapeamento nativo

1. Iniciar uma cópia da instância com ProjectE e Project Expansion, sem AutoEMC nem ProjectE Integration.
2. Verificar o EMC de itens básicos como pedregulho, pedra, terra, carvão, ferro, ouro e diamante.
3. Testar a Transmutation Table: aprender item, gastar EMC e confirmar que o item esperado é produzido.
4. Se algum valor estiver ausente, capturar o `latest.log` gerado após essa execução. Não reutilizar log de uma inicialização anterior.
5. Se necessário, ativar temporariamente `dumpToFile` em `config/ProjectE/mapping.toml` numa cópia de teste. O dump é diagnóstico local e não deve ser versionado indiscriminadamente.

### Fase 2 — receitas e cobertura

1. Instalar o exportador KubeJS numa cópia da instância e executar `/reload`.
2. Guardar o `recipe_catalog_export.json` resultante e verificar os contadores e os erros.
3. Categorizar receitas por tipo de processamento, namespace, ingredientes, saídas, quantidade, chance, fluido e subprodutos quando esses dados estiverem disponíveis.
4. Marcar receitas e itens não mapeados para revisão; não inventar saídas nem valores para campos desconhecidos.

### Fase 3 — política e exceções controladas

1. Deixar a política vazia enquanto o mapeamento nativo funcionar corretamente.
2. Adicionar overrides somente para itens que precisam de valor fixo por balanceamento, itens que o ProjectE não consegue mapear e exceções comprovadas.
3. Se o ProjectE suportar a receita normal, preferir o cálculo nativo em vez de cadastrar uma segunda cópia do valor.
4. Quando uma conversão não for coberta pelo mapper nativo, avaliar uma receita `pe_custom_conversions` do datapack após validar o esquema oficial do ProjectE para a versão instalada.

### Fase 4 — auditoria econômica

- Detectar ciclos de conversão e relações de ida e volta, em especial pedra/pedregulho, compactação/descompactação, minérios, processamento de máquinas e subprodutos.
- Considerar receitas que multiplicam saídas, probabilidades, fluidos, energia e automação. Uma receita de crafting simples não deve ser a única fonte para julgar uma cadeia de máquinas.
- Sinalizar valores gigantes, zero inesperado, valores duplicados, itens sem fonte de valor e overrides que entrem em conflito com o mapeamento nativo.
- Valores suspeitos são candidatos a revisão, não uma autorização para alterar automaticamente a economia.

### Fase 5 — critérios de conclusão

Só marcar o balanceamento como aprovado depois de:
- [ ] O jogo carregar sem erro de inicialização do ProjectE.
- [ ] Itens básicos e materiais de progressão exibirem EMC esperado.
- [ ] A Transmutation Table aprender, gastar e produzir itens normalmente.
- [ ] Relatório de cobertura e itens sem valor ser gerado e revisado.
- [ ] Ciclos e caminhos de EMC infinito conhecidos serem testados.
- [ ] O catálogo refletir as receitas da instância e versão correta.
- [ ] A atualização ser testada em uma cópia do mundo; save original e backup permanecerem intactos.

## Uso local das ferramentas

Execute os comandos a partir da raiz do repositório. Python 3.10+ é necessário apenas para as ferramentas de desenvolvimento; jogadores comuns não precisam dele para abrir o modpack.

Gerar a configuração candidata usando apenas as entradas `approved` na política:

```powershell
python tools/projecte-emc/build_custom_emc.py
```

O resultado será `build/projecte-emc/custom_emc.json`. O script valida seletores, duplicatas, EMC inteiro não negativo e justificativas. Ele não altera `config/ProjectE/custom_emc.json` automaticamente.

Executar os testes unitários:

```powershell
python -m unittest discover -s tools/projecte-emc -p "test_*.py"
```

A política inicial está vazia de propósito. Portanto, a primeira saída esperada é um arquivo válido com `entries: []`; não significa que todos os itens do ATM10 tenham sido auditados. Primeiro precisamos comprovar o mapeamento nativo e só depois adicionar overrides revisados.

## Estado legado

Antes de começar este fluxo, `config/ProjectE/custom_emc.json` continha **67.531 entradas**. Essa tabela foi gerada no período dos addons anteriores e inclui valores que precisam de revisão; por isso, ela fica no arquivo de arquivo legado apenas para comparação e recuperação. **Não deve ser tratada como a política nova nem mesclada automaticamente**. A configuração ativa começa vazia e o ProjectE volta a ser responsável pelo cálculo nativo que ele suporta.

## Operação segura

- Desenvolver e validar tudo em `work/projecte-emc-balancing`.
- Não modificar `main` automaticamente e não mesclar sem revisão.
- Não versionar logs/dumps temporários desnecessários nem substituir o save do jogador.
- Aplicar uma alteração de configuração por vez, registrar a origem e conferir o resultado num mundo de teste.
