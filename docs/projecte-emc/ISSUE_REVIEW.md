> **Documento histórico.** Esta revisão registra as issues e os sintomas observados durante a investigação original. Ela não é a arquitetura atual. Para implementar e testar EMC sem AutoEMC nem ProjectE Integration, siga [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

# ProjectE EMC — revisão das issues e diagnóstico inicial

**Branch de trabalho:** `work/projecte-emc-balancing`  
**Escopo:** ATM10 modificado, Minecraft 1.21.1 / NeoForge  
**Status:** diagnóstico por arquivos e issues; ainda falta um teste em runtime na instância.

## Conclusão principal

Antes de balancear preços, é necessário fazer o ProjectE carregar os seus mapeamentos. O relatório atual do AutoEMC informa:

```text
[AutoEMC] Skipped: ProjectE's EMC mappings never became ready.
No EMC files were changed; check the ProjectE startup log.
```

Logo, não é correto interpretar o arquivo de EMC vazio como prova de que o algoritmo de balanceamento está errado: o AutoEMC foi interrompido antes de gerar/gravar valores.

## Issues do próprio repositório

### Issue #4 — prioridade máxima
[EMC zerado: AutoEMC interrompe análise; conflito provável ProjectE Integration × Ice and Fire CE Beta.17](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/4)

A issue registra:
- ProjectE PE1.1.0, ProjectE Integration 8.4.0, Project Expansion 1.0.6 e AutoEMC 2.1.1.
- Ice and Fire Community Edition Beta.17 e Immersive Engineering 12.4.2-194.
- O log do AutoEMC termina com a mensagem de que os mapeamentos do ProjectE nunca ficaram prontos.
- `config/ProjectE/custom_emc.json` está vazio no snapshot consultado.
- A hipótese mais forte documentada é o conflito entre ProjectE Integration e Ice and Fire CE; Immersive Engineering é uma hipótese secundária.
- Novo log de 17/10/2026: uma tentativa de iniciar sem ProjectE Integration falhou porque AutoEMC 2.1.1 declara `projecteintegration >= 8.3.1` como dependência obrigatória.
- `logs/instance_audit.txt` registra eventos de remoção dos dois mods, mas o `logs/latest.log` da inicialização das 02:29 lista ProjectE 1.1.0 e Project Expansion 1.0.6 como encontrados. A evidência direta dessa execução mostra ProjectE presente e ProjectE Integration ausente; o carregamento foi abortado pela dependência obrigatória do AutoEMC.

**Interpretação:** resolver o carregamento do ProjectE vem antes de ajustar os preços.

### Issue #5 — relato original
[chat do chatgpt sobre o modpack](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/5)

O histórico registra que nenhum EMC aparece nem para pedra. A proposta antiga de remover somente ProjectE Integration mantendo AutoEMC foi invalidada pelo log atual, pois AutoEMC 2.1.1 exige essa dependência. O teste deve desativar AutoEMC junto do Integration, e manter ProjectE instalado.

### Issue #1 — inventário de mods
[mods do modpack antigo](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/1)

Serve como referência de conteúdo/versionamento da instância. Antes de mudar arquivos de configuração, conferir a versão realmente usada no lançamento e não presumir que a lista antiga é idêntica ao estado atual.

### Issue #3 — cuidado com dados da instância
[erros por tentar mandar o mundo no github enquanto eu estava jogando](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/3)

A issue registra mensagens de Git ao tentar enviar arquivos do mundo. Nesta tarefa, não adicionar saves, arquivos temporários, logs gigantes ou dados de runtime ao commit sem necessidade. Trabalhar com alterações pequenas e revisáveis.

### Issue #2 — sem relação direta com EMC
[ideias para os mods do create](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/2)

Contém ideias e imagens ligadas ao Create, mas não apresenta evidência direta sobre a falha de carregamento do ProjectE nem uma matriz de valores EMC.

## Evidência externa relacionada

- [ProjectE-Integration #176 — EMC gets wiped from all Items when present with Ice And Fire Community Edition](https://github.com/TagnumElite/ProjectE-Integration/issues/176): relata desaparecimento de EMC com ProjectE 1.1.0 e ProjectE Integration 8.3.1 ao lado de Ice and Fire CE. Um comentário do projeto Ice and Fire diz que, desde o Beta.17, a mudança no sistema de registro quebra o mapper antigo; também diz que o CE possui integração própria.
- [ProjectE-Integration #155 — possível incompatibilidade com Immersive Engineering](https://github.com/TagnumElite/ProjectE-Integration/issues/155): relata desaparecimento geral de EMC com versões específicas/mais antigas do Immersive Engineering. Como a versão local listada é 12.4.2-194, o caso exato ainda precisa ser comprovado; esta é uma segunda hipótese, não a primeira.
- [ProjectE-Integration #165 — EMC values removed in ATM10](https://github.com/TagnumElite/ProjectE-Integration/issues/165): outro relato do mesmo sintoma em ATM10, útil como evidência contextual, mas não substitui o teste na combinação exata desta instância.

Esses relatos tornam a incompatibilidade plausível, mas não confirmam por si só qual mod provoca a falha nesta instalação.

## O que existe na configuração consultada

Em `config/autoemc-common.toml`, no branch `main` consultado:
- AutoEMC está habilitado.
- `solveRecipes`, `useMapperFramework`, conversões agrupadas e fallback estão habilitados.
- `allowRecipeValueIncrease = false`, uma proteção importante para evitar que uma receita valorize artificialmente seus ingredientes.
- Existem valores-base explícitos para materiais vanilla e modded, inclusive `minecraft:cobblestone=1`, `minecraft:gravel=4` e `minecraft:dirt=1` na lista de baselines.
- Há regras de tiers e proteções para materiais avançados.

A presença desses valores no TOML **não prova que eles estão ativos no ProjectE neste momento**. O log confirma que a etapa atual do AutoEMC foi ignorada. Antes de revisar o balanceamento, confirmar qual configuração será efetivamente carregada e quais valores serão gravados.

## Plano de diagnóstico seguro

1. Fazer backup da instância e do mundo; fechar o jogo.
2. Em uma **cópia** da instância, testar primeiro ProjectE + Project Expansion + ProjectE Integration + Ice and Fire CE, desativando apenas AutoEMC. Verificar os valores de EMC.
3. Em outra cópia, manter ProjectE + Project Expansion + Ice and Fire CE, desativando **ProjectE Integration e AutoEMC juntos**. Não remover ProjectE.
4. Em cada teste, guardar o `latest.log` e o log de debug e verificar pedra, terra, diamante e a Transmutation Table.
5. Se o segundo teste funcionar e o primeiro não, a presença do Integration fica fortemente implicada. Se ambos falharem, examinar o erro original do ProjectE e isolar a hipótese de Immersive Engineering.

Para a verificação atualizada da dependência e a diferença entre o histórico de auditoria e o log da execução, consulte [`DEPENDENCY_AUDIT.md`](DEPENDENCY_AUDIT.md).
6. Somente depois de o ProjectE ficar estável, gerar e auditar os EMCs.

## Critérios para o balanceamento posterior

- Mapear conversões e receitas antes de escolher valores, em especial pedra, pedregulho, ardósia e variantes.
- Auditar ciclos de conversão e automação (geradores de pedregulho, duplicação, subprodutos, compactação/descompactação).
- Preservar progressão entre recursos comuns, minérios, materiais de máquinas, recursos raros e itens de endgame.
- Não valorizar itens criativos/infinito ou itens sem receita apenas por heurística barata.
- Produzir relatório de cobertura, itens sem EMC, conflitos, valores fora de faixa e ciclos suspeitos.
- Testar no modpack real e manter todas as mudanças na branch de trabalho até a revisão; não mesclar em `main` automaticamente.

**Limite atual:** esta nota organiza evidências e próximos passos. Ainda não foi feito teste de runtime, portanto a causa não deve ser marcada como confirmada nem os valores finais de EMC como aprovados.
