# All The Mods 10 — instalação, atualização segura e preservação do mundo

Este repositório contém uma **instância personalizada do All The Mods 10**, com mods, configurações e modificações próprias. O mundo salvo merece o mesmo cuidado que os arquivos do modpack: nunca atualize a única cópia da instância sem fazer backup.

## 1. Pré-requisitos

Antes de começar, você precisa ter:

- [CurseForge](https://www.curseforge.com/download/app) instalado.
- [Git para Windows](https://git-scm.com/downloads/win) instalado.
- Espaço livre suficiente no disco. O modpack pode ocupar aproximadamente 16 GB ou mais; o procedimento de atualização segura exige espaço adicional para uma segunda cópia temporária.

Para verificar se o Git está funcionando, abra um terminal e execute:

```powershell
git --version
```

Se aparecer o número da versão do Git, está tudo certo.

## 2. Abra a pasta do CurseForge

Abra o Explorador de Arquivos do Windows e vá até:

```text
C:\Users\SEU_USUARIO\curseforge\minecraft\Instances
```

**Importante:** substitua `SEU_USUARIO` pelo nome da pasta do seu usuário do Windows.

Essa é a pasta padrão das instâncias do Minecraft gerenciadas pelo CurseForge. Se você instalou o CurseForge em outro local, confira o diretório de modding do Minecraft nas configurações do aplicativo.

## 3. Abra o terminal nessa pasta

Com a pasta `Instances` aberta, clique com o botão direito em uma área vazia e escolha **Abrir no Terminal**. Confirme que o terminal está na pasta `Instances`.

## 4. Baixe o modpack pela primeira vez

Copie e execute este comando:

```powershell
git clone https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10.git
```

Quando terminar, deverá existir uma pasta `All-The-Mods-10` dentro de `Instances`. Não feche o terminal enquanto o Git ainda estiver baixando arquivos.

## 5. Abra o CurseForge

1. Abra o CurseForge. Se já estiver aberto, feche-o completamente e abra novamente.
2. Entre em **Minecraft** e procure a instância **All-The-Mods-10** em **My Modpacks**.
3. Selecione a instância e clique em **Play**.
4. Antes de jogar, confirme que está entrando na instância e no mundo corretos.

## 6. Atualize para a versão mais recente da `main` sem perder o save

### Regra principal: não dê `git pull` diretamente na única instância que você usa para jogar

Este repositório contém a pasta `saves/` versionada pelo Git. Isso significa que uma atualização pode trazer alterações nessa pasta, causar conflitos ou misturar o mundo que veio do repositório com o seu mundo local. **Fazer backup antes é obrigatório.** O procedimento recomendado abaixo cria uma instância nova e deixa a antiga intacta.

### Passo A — feche e faça backup

1. Saia do mundo usando **Salvar e sair**.
2. Feche o Minecraft e o CurseForge completamente.
3. Execute o bloco PowerShell abaixo na pasta `Instances`. Se o seu CurseForge usa outro diretório, ajuste a variável `$instances` antes de executar.

```powershell
$instances = Join-Path $env:USERPROFILE "curseforge\minecraft\Instances"
$current = Join-Path $instances "All-The-Mods-10"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupRoot = Join-Path $env:USERPROFILE "Documents\MinecraftBackups\All-The-Mods-10-$stamp"
$backupSaves = Join-Path $backupRoot "saves"
$next = Join-Path $instances "All-The-Mods-10-update-$stamp"

if (!(Test-Path (Join-Path $current "saves"))) {
    throw "Não encontrei a pasta saves da instância atual. Confira o caminho antes de continuar."
}
if (Test-Path $next) {
    throw "A pasta de atualização já existe. Não vou sobrescrevê-la; escolha outro nome ou horário."
}

New-Item -ItemType Directory -Path $backupSaves -Force | Out-Null
robocopy (Join-Path $current "saves") $backupSaves /E /COPY:DAT /DCOPY:DAT
if ($LASTEXITCODE -ge 8) {
    throw "O backup de saves falhou. Não continue até corrigir o backup."
}

Write-Host "Backup de saves criado em: $backupSaves"
```

**Confira o backup antes de prosseguir.** Entre na pasta indicada e confirme que seus mundos estão dentro dela. Se houver espaço suficiente, também é recomendável copiar a instância antiga inteira para um disco ou diretório de backup separado.

### Passo B — baixe a `main` em uma pasta nova

No mesmo terminal, execute:

```powershell
git clone --branch main --single-branch https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10.git $next
if ($LASTEXITCODE -ne 0) {
    throw "O clone da main falhou. A instância antiga e o backup continuam preservados."
}
```

Não clone por cima da pasta antiga. A pasta nova terá um nome parecido com `All-The-Mods-10-update-20261017-102000`.

### Passo C — coloque o seu save na instância nova

O repositório pode conter uma versão do mundo. Vamos mantê-la separada, em vez de misturá-la com seu save atual.

```powershell
$repoSaves = Join-Path $next "saves"
if (Test-Path $repoSaves) {
    Rename-Item -LiteralPath $repoSaves -NewName "saves-from-repository-$stamp"
}
New-Item -ItemType Directory -Path $repoSaves -Force | Out-Null

robocopy $backupSaves $repoSaves /E /COPY:DAT /DCOPY:DAT
if ($LASTEXITCODE -ge 8) {
    throw "A cópia do save para a nova instância falhou. Não apague nem altere a instância antiga."
}

# Preferências locais opcionais:
Copy-Item -LiteralPath (Join-Path $current "options.txt") -Destination $next -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath (Join-Path $current "servers.dat") -Destination $next -Force -ErrorAction SilentlyContinue

Write-Host "Save copiado. Instância antiga preservada em: $current"
Write-Host "Instância atualizada preparada em: $next"
```

A pasta `saves-from-repository-...` fica fora de `saves/`, portanto não será tratada como um mundo jogável pelo Minecraft. Ela preserva a cópia de save que veio do repositório caso você precise consultá-la.

### Passo D — teste antes de substituir sua instância antiga

1. Abra o CurseForge e procure a nova instância. Se ela não aparecer automaticamente, **não apague nem renomeie a antiga para tentar forçar o reconhecimento**; confirme primeiro o caminho da instância no CurseForge.
2. Inicie a nova instância e abra seu mundo copiado.
3. Confirme que o mundo abre, o inventário/personagem estão corretos, construções, máquinas, dimensões e progresso estão presentes.
4. Faça **Salvar e sair**, feche o jogo e abra novamente para confirmar que o save persistiu.
5. Só passe a usar a nova instância como principal depois desses testes.

**Não apague a instância antiga nem o backup após o primeiro lançamento.** Mantenha ambos até ter jogado com sucesso na versão nova e feito outro backup do mundo atualizado.

### Por que não atualizar em cima da pasta antiga?

Como `saves/` faz parte do histórico do repositório, `git pull` diretamente na pasta usada para jogar pode encontrar alterações locais, conflitos ou atualizações do save que veio do servidor. A atualização em uma pasta separada permite comparar e testar a nova versão sem mexer na cópia que contém seu progresso.

**Importante:** nenhum procedimento pode garantir compatibilidade de um mundo com todas as atualizações de mods. Alterações de blocos, itens, dimensões ou mods podem exigir migração. O backup é o que permite voltar atrás caso a nova versão não abra corretamente o mundo.

## 7. Problemas comuns

**O comando `git` não funciona?**

Instale o Git para Windows pelo link de pré-requisitos e tente novamente.

**Aparece uma mensagem dizendo que a pasta já existe?**

Não execute o mesmo comando repetidamente nem apague a pasta. Confira se ela contém a instância atual ou um backup. Para atualizar, use a pasta nova com sufixo `update-...`.

**O modpack não apareceu no CurseForge?**

Confirme que o clone está dentro do diretório de instâncias configurado no CurseForge. Feche e reabra o aplicativo. Se a instância nova não aparecer, mantenha a antiga intacta e verifique o caminho antes de tentar outro procedimento.

**O download parece demorado?**

O repositório contém muitos arquivos. Aguarde o terminal terminar e mantenha espaço livre suficiente, especialmente durante uma atualização com duas instâncias.

## 8. Balanceamento do ProjectE

O trabalho de EMC está sendo desenvolvido sem depender de AutoEMC ou ProjectE Integration. O plano é deixar o ProjectE fazer os cálculos nativos das receitas que ele já suporta e cadastrar manualmente apenas exceções revisadas.

Veja o [plano de implementação do EMC](docs/projecte-emc/IMPLEMENTATION_PLAN.md), a [exportação das receitas em JSON](docs/projecte-emc/RECIPE_EXPORT.md) e a [auditoria pré-merge de integridade das receitas](docs/projecte-emc/PREMERGE_RECIPE_AUDIT.md). A tabela antiga de custom EMC foi arquivada em [custom_emc.legacy-generated.json](docs/projecte-emc/archive/custom_emc.legacy-generated.json) apenas para referência; a configuração ativa começa vazia e a tabela antiga não será restaurada automaticamente.

### Ferramentas para desenvolvedores

Com Python 3.10+ instalado, na raiz do repositório:

```powershell
python tools/projecte-emc/build_custom_emc.py
python -m unittest discover -s tools/projecte-emc -p "test_*.py"
```

O primeiro comando cria uma **configuração candidata** em `build/projecte-emc/custom_emc.json`; não sobrescreve a configuração de jogo automaticamente. O segundo executa os testes do gerador. A política começa vazia de propósito: os valores devem ser adicionados somente depois de testar os mapeadores nativos e justificar cada exceção.

As alterações de desenvolvimento ficam na branch `work/projecte-emc-balancing` até serem testadas e revisadas.

---

**Repositório:** [Lucas-Belucci-Bellini/All-The-Mods-10](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10)
