# Plano de recuperação do EMC — ProjectE / AutoEMC

## Objetivo

Restabelecer EMC funcional e balanceado no ATM10 customizado, preservando a instância atual e evitando restaurar cegamente arquivos de um snapshot antigo. Este documento registra o trabalho proposto; **não declara a correção concluída**.

## Evidências já encontradas

- Snapshot histórico: commit [cb98b1f](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/commit/cb98b1f04766b4c9c7e6f84fe4b79bfe3fd5ed71).
- Nesse snapshot, `logs/modlist.txt` registra 543 mods, incluindo AutoEMC 2.1.1, ProjectE 1.1.0, ProjectE Integration 8.4.0 e Project Expansion 1.0.6.
- O mesmo snapshot não prova que o EMC funcionava: `config/ProjectE/custom_emc.json` está vazio e o estado de resolução do AutoEMC registra `knownProjectEValues: 0`.
- A auditoria anterior registra a mensagem de que os mapeamentos do ProjectE nunca ficaram prontos.
- AutoEMC 2.1.1 declara ProjectE Integration >= 8.3.1 como dependência obrigatória. Portanto, remover somente ProjectE Integration com AutoEMC instalado provoca falha de carregamento.
- A investigação aponta uma possível incompatibilidade entre ProjectE Integration e Ice and Fire Community Edition Beta.17; Immersive Engineering é uma hipótese secundária. Nenhuma das duas deve ser tratada como causa confirmada antes dos testes.
- A branch histórica de preservação é [recovery/autoemc-projecte-integration-2026-10-17](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10/tree/recovery/autoemc-projecte-integration-2026-10-17). Ela deve ser usada como referência, não como prova de uma configuração funcional.

## Plano de execução

### Fase 1 — congelar e conferir o ponto de recuperação

- [ ] Manter `main` e o mundo principal intocados durante o diagnóstico.
- [ ] Duplicar a instância do CurseForge e fazer backup do mundo antes de qualquer teste.
- [ ] Conferir os JARs e versões realmente instalados, sem confiar apenas no manifesto do ATM10 original.
- [ ] Comparar o modlist histórico e atual e registrar as diferenças relevantes.

### Fase 2 — isolar a origem da falha

Executar cada cenário em uma cópia independente da instância, registrando `latest.log` novo para cada inicialização.

1. **Baseline nativa:** manter ProjectE e Project Expansion; desativar AutoEMC e ProjectE Integration. Confirmar se o ProjectE carrega seus mapeamentos nativos.
2. **Integração isolada:** adicionar ProjectE Integration, sem AutoEMC, e testar se os EMCs continuam disponíveis.
3. **Combinação histórica:** manter AutoEMC 2.1.1 junto de ProjectE Integration 8.4.0 e testar o carregamento. Não remover Integration desse cenário, pois AutoEMC exige essa dependência.
4. **Teste de conflito:** se a falha reaparecer, repetir em cópias separadas desativando temporariamente Ice and Fire CE Beta.17. Só depois testar Immersive Engineering como hipótese secundária.
5. Não combinar mudanças de mods e mudanças de valores de EMC no mesmo teste; mudar uma variável por vez.

### Fase 3 — escolher e documentar a configuração suportada

- [ ] Escolher a combinação que inicia sem erros e mantém os mapeamentos de EMC disponíveis.
- [ ] Se AutoEMC for mantido, manter também a versão compatível de ProjectE Integration; se Integration for removido, remover AutoEMC junto.
- [ ] Não restaurar automaticamente a antiga tabela de EMC: auditar a origem, o formato e o balanceamento de qualquer arquivo recuperado.
- [ ] Preferir os mapeadores nativos do ProjectE para receitas suportadas; usar overrides manuais apenas para exceções revisadas e justificadas.
- [ ] Registrar versões exatas, hashes dos arquivos relevantes, mudanças feitas e razão da decisão.

### Fase 4 — validar EMC e receitas

- [ ] Conferir EMC de itens básicos: pedra, pedregulho, terra, carvão, ferro, ouro e diamante.
- [ ] Testar aprendizagem de itens, saldo de EMC e troca de itens pela Transmutation Table.
- [ ] Verificar uma amostra de receitas de mods e itens de alto valor para identificar valores ausentes, zero indevido ou exploração de EMC.
- [ ] Verificar se os dados/exportações de receitas têm contagens coerentes e registrar erros de serialização ou receitas que não foram capturadas.
- [ ] Salvar logs produzidos no teste atual; não usar logs antigos como prova de sucesso.
- [ ] Confirmar que o mundo pode ser carregado e salvo na cópia de teste.

### Fase 5 — revisão antes de integrar

- [ ] Anexar ao PR a matriz de cenários, resultados, logs relevantes e decisão final.
- [ ] Conferir o diff para garantir que não inclui saves, caches, arquivos temporários ou dados desnecessários.
- [ ] Pedir revisão antes de alterar ou integrar qualquer configuração na branch principal.
- [ ] Só considerar a correção concluída depois de comprovar a inicialização, mapeamentos, valores básicos, receitas e Transmutation Table em runtime.

## Critérios de aceite

A tarefa só pode ser marcada como concluída quando:

1. O cenário escolhido inicia sem erro de dependência.
2. Os mapeamentos de EMC carregam e itens básicos têm valores válidos.
3. A Transmutation Table funciona para aprender e trocar itens.
4. Os testes de receita não revelam falhas críticas de balanceamento.
5. Os logs de sucesso são do teste atual e estão disponíveis para revisão.
6. A solução mantém `main` e o mundo original protegidos até a aprovação.

## Escopo deste PR

Este PR adiciona somente o plano de trabalho. Não reinstala nem remove mods, não altera `config/ProjectE/custom_emc.json`, não afirma que o crash foi corrigido e não deve ser interpretado como autorização para mesclar uma restauração histórica sem os testes descritos.
