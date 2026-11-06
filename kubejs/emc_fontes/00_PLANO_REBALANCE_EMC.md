# Rebalanceamento global de EMC

## Objetivo

Auditar todos os itens descobertos no modpack, não apenas Mekanism Extras. A tabela mestra deve cobrir vanilla e todos os namespaces presentes nos mods instalados.

## Fonte de verdade e fluxo

1. Executar `gen_all.py` no ambiente local do modpack, com os JARs e tags da instalação.
2. O gerador continua escrevendo os valores carregados pelo ProjectE em `kubejs/data/emc_balanceado/pe_custom_conversions/00_valores_completos.json`.
3. O mesmo processo gera `kubejs/emc_fontes/00_tabela_mestra_emc.json`, com uma linha por item descoberto, inclusive itens sem EMC.
4. Revisar a tabela por namespace/mod, categoria e progressão; preencher `progression_tier`, `target_emc`, `review_status` e `review_notes`.
5. Revisar também `00_receitas_pendentes_emc.json`; receitas listadas não recebem custo automático até que seus insumos sejam modelados.
6. Só depois de revisar um grupo, transportar os valores aprovados para as fontes autorais em `kubejs/emc_fontes/` e regenerar o arquivo consumido pelo ProjectE.
7. Comparar os resultados, validar receitas reversíveis e cadeias de processamento, e testar no jogo antes de integrar.

## Critérios de balanceamento

- **Custo de obtenção:** ingredientes consumidos, quantidades, etapas e máquinas obrigatórias.
- **Progressão:** tecnologia, dimensão, estrutura, boss ou etapa necessária para obter o item.
- **Raridade e renovabilidade:** recurso comum, limitado, renovável, farmável ou exclusivo.
- **Hierarquia:** componentes equivalentes de tiers superiores devem custar mais que os inferiores, salvo justificativa explícita.
- **Cadeias de processamento:** nenhuma rota de conversão, compactação, descompactação ou processamento deve gerar EMC líquido.
- **Farms:** valor por item e rendimento por tempo precisam ser considerados em conjunto; itens renováveis não podem virar uma fonte desproporcional de EMC.
- **Exceções:** itens criativos, técnicos, de quest, de debug ou sem obtenção legítima devem permanecer sem EMC quando apropriado.

## Escala inicial

Âncoras atuais: ferro 256, ouro 2.048, diamante 8.192, nether star 139.264; Allthemodium 1.048.576, Vibranium 4.194.304, Unobtainium 16.777.216; estrela ATM 1 quintilhão (10^18). AllTheCompressed não recebe EMC, para não explodir pedra compactada nem puxar uniques para 64.

## Campos da tabela mestra

| Campo | Significado |
|---|---|
| `id` | ID completo do item (`namespace:item`) |
| `mod` | Namespace responsável |
| `current_emc` | Valor calculado atualmente; nulo se não houver EMC |
| `origin` | Origem do valor: base manual, regra de minério, heurística ou receita |
| `progression_tier` | Tier de progressão a ser atribuído na revisão |
| `target_emc` | Valor proposto após auditoria |
| `review_status` | `pending`, `reviewed`, `approved` ou `exception` |
| `review_notes` | Justificativa, dependências e exceções |

## Ordem de auditoria

1. Materiais e componentes de progressão (metais, gemas, ligas, circuitos e peças).
2. Mekanism, Mekanism Extras e demais linhas de máquinas por tier.
3. Recursos de dimensões, bosses e estruturas.
4. Itens de processamento, química, energia e armazenamento.
5. Agricultura, drops, recursos renováveis e farms.
6. Itens de todos os demais mods e conteúdo vanilla.
7. Auditoria final de receitas, conversões e balanceamento por hora de farm.

## Execução reproduzível

O gerador não presume um caminho pessoal de instalação. Informe a raiz do Minecraft/CurseForge por argumento ou variável de ambiente:

- Windows: `python -I gen_all.py "<instância ATM10>" "<pack_tags.json>" "<saída EMC.json>" "<bad_ids.txt>" --minecraft-root "<raiz Minecraft/CurseForge>"`
- Linux/macOS: use os mesmos argumentos, apontando `--minecraft-root` para a raiz equivalente da instalação.
- Para reconstruir o inventário sem reutilizar cache: acrescente `--no-cache`.
- Alternativamente, defina `ATM10_MINECRAFT_ROOT` (ou `MINECRAFT_ROOT`) e omita `--minecraft-root`.

O cache v2 é endereçado pelo SHA-256 do conjunto de entradas: JAR vanilla, JARs NeoForge e dos mods, arquivo de tags, JSONs de `kubejs/data` (exceto o namespace derivado `emc_balanceado`, que é saída do próprio gerador), lista de bloqueio e metadados da instância quando presentes. Inclusões, remoções ou alterações de conteúdo geram outra chave. A saída `00_valores_completos.json` fica dentro de `kubejs/data`; contabilizá-la como entrada faria cada execução mudar o próprio fingerprint e descartar o cache, relendo os JARs a cada rodada. O cache fica no diretório temporário do sistema e pode ser descartado com segurança. Cada execução também gera `00_metadados_geracao_emc.json`, registrando timestamp UTC, versões Minecraft/NeoForge, identidade do pack quando há manifesto, fingerprint SHA-256 e lista de arquivos usados.

## Qualidade e integração

- Toda correção do gerador deve ter teste automatizado reproduzível.
- Testes unitários devem cobrir receitas simples, múltiplas saídas, quantidades, chances, catalisadores, entradas probabilísticas e ciclos.
- Receitas com múltiplas saídas garantidas: enquanto não houver alocação de custo validada para co-produtos, cada saída recebe conservadoramente o custo integral dos insumos. Isso evita criar EMC por divisão artificial do custo, mas pode superestimar co-produtos; a política deve ser refinada com dados reais antes de revisar valores finais.
- Saídas com chance inferior a 100% ficam fora do cálculo automático até que o formato da receita tenha semântica probabilística explicitamente implementada. Saídas garantidas da mesma receita continuam sendo processadas.
- Receitas com entradas fluidas/químicas ainda não modeladas e layouts de ingredientes desconhecidos não entram no solver com custo parcial. O gerador deve listá-las em `00_receitas_pendentes_emc.json`, com ID, tipo e motivo, para revisão manual.
- Alterações de EMC precisam de comparação antes/depois e verificação de conservação nas rotas de craft, compactação e processamento.
- A integração é permitida após revisão do diff, execução bem-sucedida dos testes e validação dos dados gerados. Não integrar valores que ainda estejam pendentes.
- O responsável pelo projeto autorizou abrir PR e fazer merge quando esses critérios forem satisfeitos; isso não autoriza pular validações.

## Segurança das alterações

Todo o trabalho desta revisão fica na branch `balance/emc-global-rework-2026-11` até a validação. Não editar `main` diretamente. Valores ainda não revisados devem permanecer identificados como pendentes, em vez de receber números arbitrários.


## Diagnóstico de convergência do solver

Semântica central: uma receita nunca aumenta um EMC; ela só pode baixar o valor para a receita mais barata cujo custo completo seja conhecido (invariante do ProjectE). Uma receita completa só substitui uma incompleta quando não é mais cara. A regra antiga de "aceitar qualquer mudança" permitia inflar preços e quebrava o lock entre tiers.

Anéis contráteis: quando um ciclo de receitas tem fator multiplicativo < 1 por volta (ex.: 1 vara do blaze vira 2-4 pós em esmagadores, e a prensa da IE come 5 pós por vara), não existe ponto fixo — o preço desce geometricamente para sempre. O solver agora trava o item após quatro quedas consecutivas de metade ou mais, registra o valor travado em `00_ciclos_contrateis_pendentes_emc.json` e `00_itens_ciclos_contrateis_para_revisao.csv`, e marca a origem `contraction_cycle` na tabela mestra. Esses itens exigem revisão manual: o trava-valor é conservador e o anel precisa ser resolvido por política (ex.: recusar a receita mais cara do anel ou definir override autoral).

Cada execução do solver registra o número de passadas e atualizações por fase/tier em `00_diagnostico_convergencia_emc.json`. Se qualquer tier atingir o limite de 80 passadas ainda alterando valores, o gerador interrompe a publicação do arquivo EMC final e aponta o relatório. Isso evita tratar uma solução parcial como resultado válido.

Testes sintéticos cobrem: ciclo estável, anel de troca que não infla, ciclo de feedback positivo sem inflação, e anel contratil travado pelo amortecimento.


## Correção dos palpites

Itens que nenhuma receita alcança recebem um palpite (`FALLBACK` ou regra de sufixo). O palpite é um número provisório, não uma rota econômica: enquanto um item for palpite, o solver pode substituí-lo pelo custo da sua própria receita completa, mesmo quando esse custo é maior. Na primeira vez que uma receita precifica o item ele sai da lista de palpites e passa a valer apenas a descida estrita, então a alta nunca infla uma cadeia de receitas.

Dois efeitos colaterais dessa regra, observados em novembro de 2026: itens travados em 64 com receita própria custando milhões (capacitores do Allthemodium, máquinas MEGA de refined storage, reator de fusão e de plasma do MIM) e componentes inteiros de uma cadeia herdando o mesmo travamento. O relatório de origem na tabela mestra agora marca `heuristic_fallback` somente para o item que terminou sem preço de receita; quem recebeu preço de receita é `recipe_calculated`.

A alta por âncora continua: um palpite usado sozinho numa saída ancorada (override autoral ou regra de minério) vale a participação naquela saída (ex.: 3 fragmentos de estrela do Nether = 1 estrela). Ela só se aplica a item que ainda é palpite. Antes dessa restrição, a alta reescrevia na rodada seguinte o valor que o solver dera pela receita própria, `changed` nunca chegava a zero e as 8 rodadas eram sempre esgotadas. Conflito entre uma âncora e uma rota de craft mais barata é inconsistência de dados autorais: a revisão é da âncora, porque uma receita não pode aumentar um EMC.


## Recusa de EMC por política (`no_emc`)

`emc_value: 0` não expressa "sem EMC" — o loader do ProjectE descarta valores não positivos, e `pec_before()` também. A recusa é então uma seção própria nas fontes autorais (`values.no_emc`, com `id`/`tag` e `reason`) e vence qualquer número, inclusive o dos collections do ProjectE. O item vetado sai da base, dos overrides, das regras de minério, dos palpites e da tabela publicada; as receitas que o têm como saída são descartadas, e as que o consomem ficam sem base de preço porque insumo ausente nunca é insumo grátis. Consequência: o item não pode ser convertido, queimado no fuel table nem servir de matéria-prima para calcular EMC de outra coisa.

Motivo da primeira aplicação: o dono decidiu em 6 de novembro de 2026 que a estrela do Allthemodium é quebrada demais para existir como fonte de EMC. A família vetada é `allthetweaks:atm_star`, `allthetweaks:atm_star_block`, `allthetweaks:atm_star_shard` e as peças intermediárias `kubejs:atm_star_shard_1..5` (estas últimas nem são itens registrados no pack atual). Dentro do grafo que o gerador enxerga, a família é fechada: 1 receita produz a estrela (do bloco), 2 a consomem (bloco e crushing no fragmento), e nenhum outro item usa a estrela como ingrediente — o veto não reprecifica nada fora dela (conferido: 83628 → 83624 receitas, base 4597 → 4594, `total com EMC` 71048 → 71045). As linhas `UNIQUE_HINTS` que fixavam 10^18 para a estrela foram removidas; o veto é o único mecanismo que expressa a política. O relatório `00_itens_sem_emc_por_politica_emc.json` lista os itens vetados, o motivo e quantas receitas os consomem, e a tabela mestra mantém a linha de cada um com `origin: no_emc` e `current_emc: null`.

A pesquisa em `kubejs/server_scripts/modpack/runic_multis/recipes/star_altar.js` e `kubejs/server_scripts/modpack/atm_star_creative.js` explica por que o número antigo era arbitrário e por que a estrela é o maior item do pack: ela nasce no Star Altar do MIM (2048 EU/t) de 28 blocos de liga unobtainium-allthemodium, 15 `allthecompressed:nether_star_block_3x`, 2 blocos de liga "Awakened" encantados e os oito únicos do AllTheTweaks (oblivion shard, nexium emitter, withers compass, improbable probability device, dragon soul, philosophers fuel, pulsating black hole, dimensional seed) mais patrick star e creative essence; a mesma estrela é ingrediente das receitas KubeJS que produzem os itens criativos (ex.: `ae2:creative_energy_cell` num `powah:energizing`). Essas receitas são registradas em runtime pelo KubeJS, com tipos de máquina que nem o scanner do gerador nem o cálculo automático do ProjectE interpretam, então o único EMC que a estrela tinha era o palpite autoral de 10^18 — cerca de dez mil vezes o custo dos insumos de liga e acima do total dos próprios componentes. O valor 10^18 nunca foi derivado de receita; foi escolhido para ficar acima da faixa dos únicos a 10^17.

Um item que continue com número em `before`/`after` enquanto estiver vetado é inconsistência da fonte autoral: o `00_integridade_fontes_manuais_emc.json` registra o achado `value_conflicts_with_no_emc` (erro) porque o veto silenciosamente teria prioridade sobre o valor.

## Auditoria de saídas não interpretadas

Além das receitas pendentes por ingredientes, o gerador escreve `00_saidas_pendentes_emc.json` para receitas com uma chave de saída reconhecida pelo scanner, mas sem saída de item garantida interpretável. O relatório diferencia:
- `output_layout_unrecognized_or_non_item`: estrutura de saída ainda não suportada ou saída não é item;
- `output_items_not_in_pack_index`: ID de item foi lido, mas não está no índice de itens descobertos;
- `only_probabilistic_outputs`: a receita só apresenta saídas probabilísticas, que permanecem fora do cálculo automático.

O relatório não afirma que toda entrada pendente é uma falha: alguns formatos podem ser deliberadamente não-item. Ele cria uma fila verificável para ampliar o parser com fixtures reais, sem atribuir EMC indevido.


## Auditoria de precedência das fontes manuais

Cada geração também escreve `00_auditoria_precedencia_fontes_emc.json`. O relatório reproduz a ordem real de carregamento (`[0-9][0-9]_*.json` em ordem lexicográfica; entradas posteriores substituem anteriores) e lista somente conflitos em que o mesmo item recebe valores diferentes. Para cada conflito, registra histórico, arquivo/ seção/índice de origem e valor efetivo. Duplicatas com o mesmo valor não são tratadas como conflito. O relatório é somente leitura: não altera valores nem muda a precedência.


## Qualidade dos metadados da tabela mestra

O comando `audit_master_table.py` também gera `00_qualidade_tabela_mestra_emc.json`. Ele verifica valores EMC negativos ou não inteiros, estados de revisão desconhecidos, origem ausente e decisões revisadas sem justificativa. O relatório separa erros de avisos e é somente leitura: não corrige, remove nem atribui valores. EMC zero e campos-alvo nulos continuam válidos.


## Integridade de IDs e tiers na tabela mestra

O relatório `00_qualidade_tabela_mestra_emc.json` também valida a estrutura `namespace:item` de cada ID e confere se o namespace corresponde ao campo `mod`. Um identificador sem namespace, sem caminho ou com namespace divergente é erro de integridade. Um `progression_tier` não textual ou vazio é sinalizado como aviso. Essas verificações não inferem nem atribuem tiers e não alteram EMC.


## Integridade estrutural das fontes manuais

Cada execução também gera `00_integridade_fontes_manuais_emc.json`. O relatório verifica os documentos de valores manuais nas seções `before` e `after`: estrutura de objeto/lista, referências de item (exatamente um `id` ou `tag`), sintaxe de IDs, tags sem membros descobertos e EMC positivo inteiro. Entradas de outros tipos são ignoradas por essa validação porque não são overrides `projecte:item`. A seção `no_emc` é validada no mesmo espírito (lista, `id`/`tag`, sintaxe de ID, tag sem membros), porque um ID mal escrito ali significaria "a política não foi aplicada", e o relatório ainda marca como erro o item que tem um número em `before`/`after` e ao mesmo tempo está vetado — o veto sempre vence, então o número restante é contradição a limpar. A leitura dos overrides e da precedência também ignora estruturas malformadas sem interromper a auditoria. O relatório não corrige fontes nem atribui valores.


## Pendências conhecidas para revisão do dono

Estado verificado na execução de 6 de novembro de 2026 (18 execuções do solver, todas convergindo em no máximo 20 passadas, 0 travas de ciclo; integridade das fontes e qualidade da tabela mestra sem erros nem avisos; 71045 itens com EMC de 71048):

- `allthetweaks:atm_star`, `atm_star_block` e `atm_star_shard` estão sem EMC por decisão do dono (seção `no_emc` de `08_unicos_atm.json`). Fora da tabela publicada, o ProjectE ainda tem de encontrar zero EMC para eles no jogo: as únicas receitas registradas que os produzem formam um laço fechado estrela ⇄ bloco (+ crushing para o fragmento), sem rota vinda de um item precificado, então não há base para cálculo automático. Se aparecer rota nova (ex.: um craft de mesa aberto a partir de fragmentos), o item volta a ganhar número sozinho e é preciso revisar o veto.
- O tier dos únicos do AllTheTweaks continua sendo número autoral, não cálculo: 8 itens a 10^17 e `patrick_star` a 10^16 em `08_unicos_atm.json`. As receitas reais deles são registradas em runtime pelo KubeJS com tipos de máquina que o scanner não interpreta (`modern_industrialization:star_altar`, `powah:energizing`), então nenhuma dessas âncoras é verificável a partir dos JSONs de datapack. Modelar esses tipos de receita é o pré-requisito para qualquer precificação honesta do topo do pack.
- 16788 itens permanecem `heuristic_fallback` porque nenhuma receita completa é modelada. As filas por motivo estão em `00_receitas_pendentes_emc.json`: 4317 layouts de ingrediente não interpretados, 2804 tipos excluídos por política, 1785 entradas fluidas/químicas não modeladas e 219 receitas sem itens consumidos. Ampliar o parser com fixtures reais é o caminho; nenhum valor arbitrário deve ser atribuído antes disso.
- 4 itens do ProjectExpansion terminam no teto de clamp (`arcane_alchemical_book`, `compact_sun`, `final_star`, `gargantuan_star_omega`): o custo calculado passa de `Long.MAX_VALUE - 2` e todos ficam no mesmo número. Precisam de valor autoral explicito, porque EMC acima disso não é representável no jogo.
- 1 conflito de precedência entre fontes autorais: `irons_spellbooks:pyrium_ingot` vale 4096 em `03_metais_e_gemas.json` e 122880 em `09_endgame_e_sem_receita.json`; o último vence por ordem lexicográfica. Ver `00_auditoria_precedencia_fontes_emc.json`.
- 55 overrides estão nas filas "acima do custo de receita suportada" (32) e "possivelmente acima, revisar" (23) de `00_auditoria_overrides_vs_receitas.json`. São candidatos a redução de âncora, não erros automáticos.
- `minecraft:blaze_powder` fica em 61 enquanto a vara vale 1536: há rota de esmagamento que rende muitos pós e nenhuma receita inversa, então o pós é a rota barata e a âncora da vara não desce. Se isso for exploit no jogo, a correção é override autoral do pós, não mudança do solver.
- EMC 1 em vidro, blocos de pedra e variantes decorativas (chipped/rechiseled) é consistente com o ProjectE: fundição e corte não adicionam EMC por padrão.
