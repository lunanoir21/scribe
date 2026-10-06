import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// Integration point: one `ScribeHost {}` in the shell root.
// Bind a key to:  qs -p .../Shell.qml ipc call scribe start
Scope {
    id: host

    // idle -> capturing -> selecting -> reading -> result
    property string phase: "idle"
    property var cfg: ({ langs: "tur+eng", autoCopy: false, joinLines: true, minConfidence: 60, highlight: "#8ab4f8", closeAfterCopy: true })

    property var targetScreen: null
    property string shotPath: ""
    property rect selRect: Qt.rect(0, 0, 0, 0)
    property var words: []
    property string resultStatus: "ok"
    property int resultConf: 0

    readonly property string baseDir: Qt.resolvedUrl("..").toString().replace(/^file:\/\//, "")
    readonly property string script: baseDir + "scribe.sh"

    function notify(msg) {
        Quickshell.execDetached(["notify-send", "-a", "scribe", "scribe", msg]);
    }

    function reset() {
        phase = "idle";
        words = [];
    }

    function start() {
        if (phase !== "idle")
            return;
        var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : "";
        var scr = null;
        for (var i = 0; i < Quickshell.screens.length; i++)
            if (Quickshell.screens[i].name === name)
                scr = Quickshell.screens[i];
        if (!scr && Quickshell.screens.length)
            scr = Quickshell.screens[0];
        targetScreen = scr;
        phase = "capturing";
        grabProc.command = [script, "shot", scr ? scr.name : ""];
        grabProc.running = true;
    }

    // language packs + settings panel
    property var installed: []
    property string pmName: ""
    property string osName: ""
    property string installing: ""
    property int installPct: 0
    property string installMsg: ""
    readonly property string langsPy: baseDir + "langs.py"

    function refreshLangs() {
        infoProc.command = ["python3", "-I", langsPy, "info"];
        infoProc.running = true;
    }

    function installLang(code) {
        if (installing !== "")
            return;
        installing = code;
        installPct = 0;
        installMsg = "";
        installProc.command = ["python3", "-I", langsPy, "install", code];
        installProc.running = true;
    }

    function setCfg(key, value) {
        var next = Object.assign({}, cfg);
        next[key] = value;
        cfg = next;
        saveProc.command = ["python3", "-I", "-c", "import sys; open(sys.argv[1], 'w').write(sys.argv[2] + '\\n')",
                            baseDir + "settings.json", JSON.stringify(next, null, 2)];
        saveProc.running = true;
    }

    property var testRect: null
    property string devSel: ""

    function pick(x, y, w, h, scale) {
        selRect = Qt.rect(x, y, w, h);
        phase = "reading";
        readProc.command = [script, "read", shotPath, String(x), String(y), String(w), String(h), String(scale), cfg.langs];
        readProc.running = true;
    }

    function copy(text) {
        copyProc.command = ["sh", "-c", "printf %s \"$1\" | wl-copy", "sh", text];
        copyProc.running = true;
    }

    IpcHandler {
        target: "scribe"
        function start(): void { host.start(); }
        function cancel(): void { host.reset(); }
        // dev helper: open the settings panel of the running overlay
        function devopen(): void { if (lensLoader.item) lensLoader.item.settingsOpen = true; }
        // dev helper: skip the drag and read this region (logical px) straight away
        function testsel(x: real, y: real, w: real, h: real, lo: int, hi: int): void {
            host.devSel = lo + "," + hi;
            host.testRect = { x: x, y: y, w: w, h: h };
            host.start();
        }
        function test(x: real, y: real, w: real, h: real): void {
            host.testRect = { x: x, y: y, w: w, h: h };
            host.start();
        }
    }

    FileView {
        path: host.baseDir + "settings.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: {
            try {
                host.cfg = Object.assign({}, host.cfg, JSON.parse(text()));
            } catch (e) {
                console.warn("scribe: settings.json unreadable:", e);
            }
        }
    }

    Process {
        id: grabProc
        stdout: StdioCollector {
            onStreamFinished: {
                var p = text.trim();
                if (p !== "") {
                    host.shotPath = p;
                    host.phase = "selecting";
                    if (host.testRect) {
                        var r = host.testRect;
                        host.testRect = null;
                        host.pick(r.x, r.y, r.w, r.h, 1);
                    }
                }
            }
        }
        onExited: code => {
            if (code !== 0) {
                host.notify("Ekran görüntüsü alınamadı (grim).");
                host.reset();
            }
        }
    }

    Process {
        id: readProc
        stdout: StdioCollector {
            onStreamFinished: {
                var out = [], conf = 0, nolang = false;
                var parIds = {}, lineIds = {}, np = 0, nl = 0;
                var lines = text.split("\n");
                for (var i = 0; i < lines.length; i++) {
                    var f = lines[i].split("\t");
                    if (f[0] === "W" && f.length >= 8) {
                        if (parIds[f[1]] === undefined) parIds[f[1]] = np++;
                        if (lineIds[f[2]] === undefined) lineIds[f[2]] = nl++;
                        out.push({ par: parIds[f[1]], line: lineIds[f[2]], x: parseFloat(f[3]), y: parseFloat(f[4]), w: parseFloat(f[5]), h: parseFloat(f[6]), t: f.slice(7).join("\t") });
                    } else if (f[0] === "CONF") {
                        conf = parseInt(f[1] || "0");
                    } else if (f[0] === "ERR" && f[1] === "nolang") {
                        nolang = true;
                    }
                }
                host.resultConf = conf;
                host.words = out;
                if (nolang) {
                    host.resultStatus = "nolang";
                    host.notify("Dil paketi eksik: sudo pacman -S --needed tesseract-data-eng tesseract-data-tur");
                } else if (out.length === 0) {
                    host.resultStatus = "empty";
                } else if (conf < host.cfg.minConfidence) {
                    host.resultStatus = "low";
                } else {
                    host.resultStatus = "ok";
                }
                host.phase = "result";
            }
        }
        onExited: code => {
            if (code !== 0 && code !== 2) {
                host.notify("Okuma başarısız oldu (kod " + code + ").");
                host.reset();
            }
        }
    }

    Process { id: copyProc }
    Process { id: saveProc }

    Process {
        id: infoProc
        stdout: StdioCollector {
            onStreamFinished: {
                var codes = [], lines = text.split("\n");
                for (var i = 0; i < lines.length; i++) {
                    var f = lines[i].split("\t");
                    if (f[0] === "PM") { host.pmName = f[1] || ""; host.osName = f[2] || ""; }
                    else if (f[0] === "L") codes.push(f[1]);
                }
                host.installed = codes;
            }
        }
    }

    Process {
        id: installProc
        stdout: SplitParser {
            onRead: line => {
                var f = line.split("\t");
                if (f[0] === "MSG") host.installMsg = f[1] || "";
                else if (f[0] === "PCT") host.installPct = parseInt(f[1] || "0");
            }
        }
        onExited: code => {
            host.installing = "";
            host.installPct = 0;
            if (code !== 0 && host.installMsg === "")
                host.installMsg = "Kurulum başarısız oldu.";
            host.refreshLangs();
        }
    }

    Component.onCompleted: refreshLangs()

    Loader {
        id: lensLoader
        active: host.phase === "selecting" || host.phase === "reading" || host.phase === "result"
        sourceComponent: ScribeLens {
            screen: host.targetScreen
            shot: host.shotPath
            phase: host.phase === "selecting" ? "select" : (host.phase === "reading" ? "reading" : "result")
            words: host.words
            status: host.resultStatus
            confidence: host.resultConf
            autoSelect: host.cfg.autoCopy
            joinLines: host.cfg.joinLines
            closeAfterCopy: host.cfg.closeAfterCopy
            highlight: host.cfg.highlight
            devSel: host.devSel
            cfg: host.cfg
            installed: host.installed
            installing: host.installing
            installPct: host.installPct
            installMsg: host.installMsg
            pmName: host.pmName
            osName: host.osName
            onSetCfg: (k, v) => host.setCfg(k, v)
            onInstallLang: code => host.installLang(code)
            onSettingsOpened: host.refreshLangs()
            rect: host.selRect
            onCancelled: host.reset()
            onCopyText: (t, n) => host.copy(t)
            onPicked: (x, y, w, h, scale) => host.pick(x, y, w, h, scale)
        }
    }
}
