# All The Mods 10 — Como baixar e instalar

Este repositório contém uma **versão personalizada do All The Mods 10**, com configurações e modificações próprias.

## 1. Pré-requisitos

Antes de começar, você precisa ter:

- [CurseForge](https://www.curseforge.com/download/app) instalado.
- [Git para Windows](https://git-scm.com/downloads/win) instalado.
- Espaço livre suficiente no disco. O modpack pode ocupar aproximadamente 16 GB ou mais.

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

Por exemplo, se o usuário do computador for `Joao`, o caminho será:

```text
C:\Users\Joao\curseforge\minecraft\Instances
```

Essa é a pasta onde ficam as instâncias do Minecraft gerenciadas pelo CurseForge. Se você instalou o CurseForge em outro local, abra as configurações do aplicativo e confira o diretório de modding do Minecraft.

## 3. Abra o terminal nessa pasta

Com a pasta `Instances` aberta, clique com o botão direito em uma área vazia e escolha **Abrir no Terminal**.

Confirme que o terminal está na pasta `Instances`.

## 4. Baixe o modpack

Copie e execute este único comando:

```powershell
git clone https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10.git
```

Agora, aguarde o Git terminar de baixar os arquivos. Não feche o terminal durante o processo.

Quando terminar, deverá existir uma pasta com este caminho:

```text
C:\Users\SEU_USUARIO\curseforge\minecraft\Instances\All-The-Mods-10
```

Dentro dela estarão os arquivos e as pastas da instância.

## 5. Abra o CurseForge

Depois que o download terminar:

1. Abra o CurseForge. Se ele já estiver aberto, feche o aplicativo completamente e abra novamente.
2. Entre na seção **Minecraft** e procure a lista de modpacks, em **My Modpacks**.
3. Procure a instância **All-The-Mods-10**.
4. Se ela aparecer, selecione-a e clique em **Play** para iniciar.

Pronto! O repositório foi baixado para a pasta de instâncias do Minecraft.

## Problemas comuns

**O comando `git` não funciona?**

Instale o Git para Windows pelo link disponível na seção de pré-requisitos e tente novamente.

**Aparece uma mensagem dizendo que a pasta já existe?**

O Git encontrou uma pasta chamada `All-The-Mods-10` no local de destino. Não execute o mesmo comando repetidamente nem apague a pasta sem verificar seu conteúdo primeiro.

**O modpack não apareceu no CurseForge?**

Verifique se a pasta foi criada diretamente dentro de `Instances`, feche e reabra o CurseForge e confirme o caminho configurado nas opções do Minecraft. Se continuar sem aparecer, será necessário investigar o reconhecimento da instância pelo aplicativo.

**O download parece demorado?**

O repositório contém muitos arquivos e pode ser grande. Aguarde o terminal terminar o processo e mantenha espaço livre suficiente no disco.

---

**Repositório:** [Lucas-Belucci-Bellini/All-The-Mods-10](https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10)

**Comando de instalação:**

```powershell
git clone https://github.com/Lucas-Belucci-Bellini/All-The-Mods-10.git
```
