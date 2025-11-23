"use strict";
// Helper function to send log messages to Python
function sendLog(message, data) {
    const logInfo = {
        type: "log",
        message: message,
        data: data
    };
    if (window.bridge && window.bridge.fromJs) {
        window.bridge.fromJs(JSON.stringify(logInfo));
    }
    else {
        console.log("[JS Log]", message, data);
    }
}
// Main application code
let stage = new NGL.Stage("viewport", { backgroundColor: "black" });
// Resize handling
window.addEventListener("resize", function () {
    stage.handleResize();
}, false);
// Keep current component reference
let currentComponent = null;
// Function to extract unique residue names from PDB text
function extractUniqueResnames(pdbText) {
    const resnames = new Set();
    const lines = pdbText.split('\n');
    for (const line of lines) {
        if (line.startsWith('ATOM') || line.startsWith('HETATM')) {
            // Resname is at columns 18-20 (0-indexed: 17-19)
            const resname = line.substring(17, 21).trim();
            if (resname) {
                resnames.add(resname);
            }
        }
    }
    return Array.from(resnames).sort();
}
// Function to generate distinct colors for residue names
function generateColorScheme(resnames) {
    const colorScheme = {};
    const count = resnames.length;
    resnames.forEach((resname, index) => {
        // Generate colors using HSL with evenly distributed hues
        const hue = (index * 360) / count;
        const saturation = 70;
        const lightness = 50;
        colorScheme[resname] = `hsl(${hue}, ${saturation}%, ${lightness}%)`;
    });
    colorScheme["*"] = "white";
    return colorScheme;
}
// Load PDB text from Python by calling this function
function loadPDBFromText(pdbText) {
    // Remove previous comp if any
    if (currentComponent) {
        try {
            currentComponent.removeAllRepresentations();
            currentComponent.remove();
        }
        catch (e) {
            // Ignore errors during cleanup
        }
        currentComponent = null;
    }
    // Extract unique residue names and create color scheme
    const uniqueResnames = extractUniqueResnames(pdbText);
    const colorScheme = generateColorScheme(uniqueResnames);
    sendLog("Detected residue names", { resnames: uniqueResnames, colorScheme });
    // Create Blob to load as file
    const blob = new Blob([pdbText], { type: 'text/plain' });
    stage.loadFile(blob, { ext: "pdb" }).then(function (o) {
        currentComponent = o;
        // Add a representation for each residue name with its custom color
        uniqueResnames.forEach((resname) => {
            o.addRepresentation("ball+stick", {
                sele: `[${resname}]`,
                color: colorScheme[resname],
            });
        });
        o.autoView(); // Center view on load
    }).catch(function (err) {
        console.error("NGL load error:", err);
    });
}
let selectionRepresentation = null;
function highlightAtoms(data) {
    sendLog("highlightAtoms called", { serials: data.serials });
    if (selectionRepresentation) {
        try {
            currentComponent === null || currentComponent === void 0 ? void 0 : currentComponent.removeRepresentation(selectionRepresentation);
        }
        catch (e) {
            // Ignore errors during cleanup
        }
        selectionRepresentation = null;
    }
    if (data.serials.length > 0 && currentComponent) {
        const selectionString = data.serials.map(s => `@${s - 1}`).join(" or ");
        sendLog("Creating selection representation", { selectionString });
        selectionRepresentation = currentComponent.addRepresentation("ball+stick", {
            sele: selectionString,
            color: "#00ff00",
            radiusScale: 1.5
        });
    }
    else {
        sendLog("Clearing selection", { reason: data.serials.length === 0 ? "empty serials" : "no component" });
    }
}
// WebChannel bridge
new QWebChannel(qt.webChannelTransport, function (channel) {
    window.bridge = channel.objects.bridge;
    // Connect signal after bridge is ready
    window.bridge.sendMessage.connect(function (pdbText) {
        // Store last for simple reload in selection visual feedback
        window._last_pdb_text = pdbText;
        loadPDBFromText(pdbText);
    });
});
// Picking: on click, use stage.pick
stage.signals.clicked.add(function (pickData) {
    // pickData is { picked: true/false, atom: NGL.AtomProxy, ... }
    if (!pickData || !pickData.atom)
        return;
    const atom = pickData.atom;
    const info = {
        type: "pick",
        chain: atom.chainname,
        resno: atom.resno,
        resname: atom.resname,
        atomname: atom.atomname,
        serial: atom.serial
    };
    // Send to Python
    if (window.bridge && window.bridge.fromJs) {
        window.bridge.fromJs(JSON.stringify(info));
    }
});
// Expose functions to global scope for Python to call via runJavaScript
window.loadPDBFromText = loadPDBFromText;
window.highlightAtoms = highlightAtoms;
