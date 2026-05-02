# Joystick Shortcuts

App utilitário pra Windows que transforma botões de um controle XInput (Xbox / 8BitDo / GameSir / Razer / paddles do Elite, etc.) em atalhos globais de teclado, comandos de mídia e launchers de aplicativo. Roda em background no system tray e tem opção de prioridade alta pra continuar respondendo enquanto um jogo está rodando em primeiro plano.

## Recursos

- Quantos atalhos quiser, organizados em **perfis** alternáveis pelo tray ou pela GUI
- Cada atalho dispara: **tecla única**, **combinação com modificadores** (Ctrl / Shift / Alt / Win), **ações de mídia/volume**, ou **lança um app/URL**
- Modos de disparo: ao pressionar, ao soltar, ou ao segurar por X ms
- **Prioridade alta** automática (`HIGH_PRIORITY_CLASS`) — aparece como "Alta" no Task Manager
- **Auto-start** com Windows (HKCU Run key)
- **Minimiza pro tray** ao iniciar
- Botão de **pausa global** pra desligar todos os atalhos sem fechar o app

Botões suportados: `A`, `B`, `X`, `Y`, `LB`, `RB`, `LT`, `RT`, `BACK`, `START`, `LS` (clique), `RS` (clique), e DPad (`UP`/`DOWN`/`LEFT`/`RIGHT`).

## Rodando do código (dev)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

A primeira execução cria `%APPDATA%\JoystickShortcuts\config.json` com um perfil "Default" vazio. Clique em **+ Adicionar atalho** pra começar.

## Empacotando como `.exe`

```powershell
.\build.ps1
```

Gera `dist\JoystickShortcuts.exe` (single-file, sem console). Coloque onde quiser e marque "Iniciar com Windows" na GUI — o registry vai apontar pro caminho atual do `.exe`.

## Caveats

- **Steam Input / Xbox Game Bar**: o XInput é leitura compartilhada, então o polling não conflita. Mas se o Steam estiver remapeando o controle pra teclado, os dois sistemas podem disparar a mesma ação. Se isso acontecer, desabilite Steam Input pro jogo em questão.
- **Botão Guide / Xbox**: não exposto pelo XInput público; não dá pra capturar.
- **Controles aftermarket com botões "extras"**: a maioria mapeia os paddles/macros pra inputs XInput existentes via firmware ou app companion. Configure o controle pra mapear o paddle traseiro pra `LB`, `RB` ou outro botão livre, e bind aqui no Joystick Shortcuts.
- **`keyboard` lib**: não precisa de admin pra `keyboard.send()`. Não capturamos teclas globalmente — a captura de tecla acontece só no diálogo de edição que está em foco.

## Estrutura do projeto

```
main.py                       entry point: priority bump → tray + GUI
app/
├─ models.py                  dataclasses (Action, Binding, Profile, AppConfig)
├─ profile_manager.py         load/save JSON em %APPDATA%
├─ xinput_poller.py           QThread polling 120Hz com edge detection
├─ actions.py                 executor (key/combo/media/launch) + Dispatcher
├─ system/
│  ├─ priority.py             SetPriorityClass via ctypes
│  └─ autostart.py            HKCU Run key
└─ gui/
   ├─ main_window.py          janela principal, tabela, perfis, settings
   ├─ binding_dialog.py       diálogo de criar/editar atalho
   ├─ capture_widgets.py      captura de botão e tecla
   └─ tray.py                 ícone do system tray
```
