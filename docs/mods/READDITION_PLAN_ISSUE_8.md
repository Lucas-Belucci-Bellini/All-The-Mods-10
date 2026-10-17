# Plano de readição dos mods — Issue #8

**Branch-base:** `main` (ATM10 original, snapshot de `backup-do-modpack`)  
**Versão-base registrada:** ATM10 8.3, Minecraft 1.21.1, NeoForge 21.1.259  
**Fonte da lista:** [Issue #8 — mods](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/8)  
**Diagnóstico relevante:** [Issue #4 — EMC zerado / ProjectE Integration × Ice and Fire CE](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/4)  
**Status:** plano de execução. Nenhum mod foi readicionado por este documento.

## Objetivo

Reconstruir, em etapas pequenas e testáveis, as personalizações registradas na Issue #8 sem trazer de volta os dois componentes associados ao problema de EMC: **AutoEMC 2.1.1** e **ProjectE Integration 8.4.0**.

A branch `main` deve continuar sendo a referência limpa do ATM10 original. Toda readição deve acontecer primeiro em uma cópia local da instância e ser versionada numa branch de trabalho, nunca diretamente sobre `main`.

## Decisões de inclusão e exclusão

### Não readicionar nesta rodada

| Arquivo da Issue #8 | Decisão | Motivo |
|---|---|---|
| `autoemc-2.1.1.jar` | **Excluir** | A Issue #4 registra que o AutoEMC interrompeu a análise porque os mapeamentos do ProjectE não ficaram prontos. Além disso, a versão 2.1.1 exige ProjectE Integration `>= 8.3.1`. |
| `ProjectE_Integration-1.21.1-8.4.0.jar` | **Excluir** | Forte suspeita de conflito com Ice and Fire Community Edition Beta.17; a Issue #4 relaciona o sintoma à issue upstream [ProjectE-Integration #176](https://github.com/TagnumElite/ProjectE-Integration/issues/176). Só reconsiderar com versão/correção comprovada e teste controlado. |
| `chisels-and-bits-fabric-21.1.22.jar` | **Excluir** | A instância é NeoForge. A Issue #8 também lista a build NeoForge do mesmo mod; não instalar a variante Fabric junto. |

**Não remover Ice and Fire CE da base por causa desta hipótese.** O plano é primeiro manter o mod da base e deixar ProjectE Integration de fora. A causa exata precisa de teste, mas não há motivo documentado para remover o próprio Ice and Fire.

### Manter na lista para readição controlada

ProjectE e seus outros addons não devem ser confundidos com os dois componentes excluídos. **ProjectE permanece candidato a ser readicionado**, porque é o sistema de EMC que queremos testar. Project Expansion, AppliedE e Apotheosis EMC entram separadamente depois que o ProjectE puro passar no teste básico.

Os demais itens da Issue #8 não têm evidência suficiente neste relatório para serem rotulados como causadores do problema de EMC. Isso não prova que todos sejam compatíveis: cada um precisa ser confirmado com a versão correta, dependências e teste.

## Fase 0 — preparação e proteção

- [ ] Criar uma cópia completa da instância do CurseForge, separada da instância usada para jogar.
- [ ] Fazer backup do mundo e confirmar como restaurá-lo.
- [ ] Confirmar que a cópia do ATM10 original inicia sem os mods da Issue #8 e consegue abrir/criar um mundo de teste.
- [ ] Guardar o `latest.log` de referência da inicialização limpa.
- [ ] Registrar lista de mods, versões e hashes antes de cada etapa.
- [ ] Não copiar saves, caches, logs pessoais, `local/`, arquivos temporários ou configurações geradas sem necessidade para os commits.
- [ ] Não restaurar ainda a tabela histórica gigante `config/ProjectE/custom_emc.json`; seus valores precisam de auditoria separada.

**Critério para avançar:** o ATM10 original inicia e o mundo de teste abre sem erro.

## Fase 1 — ProjectE e EMC nativo

Adicionar somente o arquivo aprovado da versão alvo:

1. [ ] `ProjectE-1.21.1-PE1.1.0.jar`
2. [ ] Iniciar o jogo e confirmar no log que o ProjectE carrega sem falha.
3. [ ] Verificar EMC de pedra, pedregulho, terra, carvão, ferro, ouro e diamante.
4. [ ] Testar aprender item e trocar itens na Transmutation Table, quando disponível.
5. [ ] Guardar logs novos e o resultado de cada verificação.

Se o ProjectE puro falhar, parar aqui e investigar o log. Não acrescentar outros addons para tentar mascarar a causa.

### Fase 1B — addons relacionados a EMC, um de cada vez

Avançar somente se a Fase 1 passar. Antes de cada adição, conferir o metadata do JAR e as dependências requeridas:

- [ ] `projectexpansion-1.21.1-1.0.6.jar`
- [ ] Testar inicialização, EMC básico e a função do ProjectE após a adição.
- [ ] `appliede-1.0.8-beta.jar`
- [ ] Testar novamente e conferir as integrações/receitas relacionadas.
- [ ] `apotheosis_emc-0.1.0+neoforge-1.21.1.jar`
- [ ] Testar novamente e conferir as integrações/receitas relacionadas.

Se um addon falhar, removê-lo apenas da cópia de teste e repetir para identificar a mudança que dispara o erro. Não adicionar dois addons de uma vez nesta fase. AutoEMC e ProjectE Integration permanecem excluídos.

**Critério para avançar:** o ProjectE continua carregando mapeamentos e o EMC básico funciona depois de cada addon aprovado.

## Fase 2 — bibliotecas e famílias de mods

Adicionar os itens a seguir em grupos pequenos, apenas após confirmar as dependências no metadata dos JARs para Minecraft 1.21.1/NeoForge.

### 2A. Biomes O' Plenty

- [ ] `GlitchCore-neoforge-1.21.1-2.1.0.2.jar`
- [ ] `BiomesOPlenty-neoforge-1.21.1-21.1.0.14.jar`
- [ ] `puzzleslib-v21.1.64-mc1.21.1+neoforge.jar`

Verificar dependências e versões antes de iniciar. Se houver erro de dependência, resolver o requisito exato antes de continuar.

### 2B. Chisels & Bits e Translocators

- [ ] `sable-neoforge-1.21.1-2.0.6.jar`
- [ ] `chisels-and-bits-neoforge-21.1.33.jar` — usar somente a build NeoForge, não a Fabric.
- [ ] `CBMultipart-1.21.1-3.5.0.155.jar`
- [ ] `Translocators-1.21.1-2.8.0.89.jar`

Confirmar as dependências de cada JAR. Testar primeiro Chisels & Bits com suas bibliotecas; testar Translocators e CBMultipart em seguida, sem assumir que precisam ser instalados todos de uma vez.

### 2C. Create e addons

Adicionar um por vez, iniciando e testando após cada inclusão:

- [ ] `create-new-age-1.2.0+neoforge-mc1.21.1.jar`
- [ ] `createendertransmission-2.1.1-1.21.1.jar`
- [ ] `create-aeronautics-bundled-1.21.1-1.3.2.jar`

Conferir os requisitos das versões exatas e fazer um teste dentro de um mundo descartável. Aeronautics deve ser introduzido por último deste grupo por ser uma integração mais abrangente com Create.

### 2D. Mekanism Extras e melhorias de armazenamento

- [ ] `mekanism_extras-1.21.1-1.4.1.jar`
- [ ] `backpack_allthemodium_upgrade-2.4.jar`
- [ ] `storage_allthemodium_upgrade-2.0.1.jar`

Confirmar que os mods base necessários estão instalados nas versões compatíveis. Verificar abertura de inventários, receitas e funcionamento das upgrades.

## Fase 3 — outros mods da Issue #8

Adicionar individualmente, nesta ordem sugerida, e registrar o resultado de cada um:

- [ ] `ae2extras-neoforge-1.21.1-0.jar`
- [ ] `extrautilitiesreborn-1.0.1-neoforge-1.21.1.jar`
- [ ] `ChickenChunks-1.21.1-2.12.0.103.jar`
- [ ] `easy_mob_farm-neoforge-1.21.1-11.0.0.jar`
- [ ] `EnchantingInfuser-v21.1.4-1.21.1-NeoForge.jar`
- [ ] `inzhefopcore-1.0.0-neoforge-1.21.1.jar` — identificar sua função e dependências antes de instalar; não assumir compatibilidade pelo nome.
- [ ] `Essential_1-5-0-1_neoforge_1-21-1.jar`
- [ ] `packetfixer-3.3.1-1.20.5-1.21.X-merged.jar` — adicionar por último, pois modifica tratamento de pacotes; verificar que a versão indica suporte à combinação alvo de Minecraft e NeoForge.

Se qualquer item provocar erro, não continuar acumulando alterações. Registrar o arquivo/JAR recém-adicionado, guardar o log e repetir a inicialização sem essa mudança para confirmar a relação.

## Fase 4 — resource packs da Issue #8

Resource packs não são mods Java. Adicioná-los e ativá-los só depois de validar as fases de mods; não ativar todos de uma só vez. Manter uma lista de habilitados e testar tela inicial, inventário, mundo, texturas e sons após cada lote pequeno.

Lista de resource packs registrada na Issue #8:

- [ ] `[Compressed] Alternative Rain Sounds 1.21-1.21.1.zip`
- [ ] `AmbientSound6_R13.zip`
- [ ] `Better Caves 3D.zip`
- [ ] `Better+Lanterns+v1.2(mc-1.21).zip`
- [ ] `Better-Leaves-9.6.zip`
- [ ] `crops3d1.21.1.zip`
- [ ] `cubic-sun-moon-v1.8.5.zip`
- [ ] `Drigo 3D Lantern's x Punchy.zip`
- [ ] `DynamicSurroundings_R25.zip`
- [ ] `Enchantment Glows v1.12.1.zip`
- [ ] `EnderEyes_26.3_v3.1.zip`
- [ ] `Farm 3D.zip`
- [ ] `Fast Better Grass.zip`
- [ ] `GEO - v1.115.0.zip`
- [ ] `ImmersiveWeather_R12.zip`
- [ ] `Undopia_3D_Iron_Bars_1.21.x_v.1.0.zip`
- [ ] `xali's enchanted book v1.0.0.zip`
- [ ] `§eArmorstands§8-§eReimagined§0_§8[v1.3]§0.zip`
- [ ] `§eTorches§8-§eReimagined§0_§8[v1.8]§0.zip`
- [ ] `§l3D§f+Ladders+v1.2(mc-1.21).zip`

## Protocolo obrigatório após cada adição

Registrar cada teste em uma tabela ou comentário de PR:

| Campo | O que registrar |
|---|---|
| Etapa | Número e nome da etapa |
| Arquivo adicionado | Nome exato do JAR/ZIP e versão |
| Dependências | Presentes e compatíveis? |
| Inicialização | Sucesso/falha |
| Mundo de teste | Abriu e salvou normalmente? |
| EMC | Valores básicos e Transmutation Table continuam funcionando? |
| Log | Caminho para o `latest.log` novo e para crash report, se existir |
| Decisão | Manter, remover da cópia ou investigar |

Regras:
- Mudar uma variável por vez, especialmente durante a investigação de EMC.
- Usar logs gerados depois da alteração; não reutilizar `latest.log` de uma sessão antiga como prova.
- Não testar mudanças inicialmente no mundo principal.
- Não aceitar uma inicialização como prova suficiente: validar as funções introduzidas.
- Se o teste falhar, parar, isolar a última mudança e documentar a causa antes de continuar.

## Critérios para abrir o PR final

- [ ] Todos os JARs a readicionar têm versão e dependências verificadas.
- [ ] AutoEMC e ProjectE Integration permanecem fora desta rodada.
- [ ] A build Fabric de Chisels & Bits não foi incluída na instância NeoForge.
- [ ] Os addons de ProjectE foram testados individualmente.
- [ ] O EMC básico permanece funcional após cada etapa aprovada.
- [ ] O jogo inicia, um mundo de teste abre e salva sem erros novos.
- [ ] Resource packs foram separados dos mods e testados por etapas.
- [ ] O diff não contém saves, caches ou arquivos de runtime desnecessários.
- [ ] Logs e matriz de testes estão anexados à descrição do PR.
- [ ] A branch `main` permanece igual ao ATM10 original até a revisão humana.

## Referências

- [Issue #8 — lista de mods e resource packs a adicionar](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/8)
- [Issue #4 — problema de EMC e hipótese de conflito](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/issues/4)
- [ProjectE-Integration #176 — relato de EMC apagado com Ice and Fire Community Edition](https://github.com/TagnumElite/ProjectE-Integration/issues/176)
- [Branch `backup-do-modpack` — baseline original](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/tree/backup-do-modpack)
- [Branch de trabalho deste documento](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/tree/docs/mod-readdition-plan)

**Nota final:** este documento planeja a readição; não instala os mods nem garante antecipadamente que todos os itens restantes funcionem juntos. Qualquer incompatibilidade descoberta nos testes deve ser registrada antes de continuar.
