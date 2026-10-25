const MAX_GOLD = 65000;
const MAX_GEARBITS = 33000;
const FORMAT_CONSTANT = new TextEncoder().encode(" Copyright (C) 2010 Activision. All Rights Reserved. ");
const INITIALIZABLE_TYPES = new Set(["Skylander", "Giant", "LightCore", "Swapper", "Trap Master", "SuperCharger", "Sensei"]);
const FRESH_CHARACTER_BLOCKS = {
  0x24: "00000000000700000001a5f8aea1f159",
  0x25: "00000000000001010000000000000000",
  0x29: "140d1b09ea070000000000000e081901",
  0x2a: "140d1b09ea0700000000000000000000",
  0x2c: "c7ff0180ff0000000000000000000000",
  0x2d: "545b0100000000000000000000000000",
};
const $ = (id) => document.getElementById(id);
const ui = {
  filePicker: $("file-picker"), folderPicker: $("folder-picker"), chooseFolder: $("choose-folder"), clear: $("clear-button"),
  empty: $("empty-state"), view: $("preview-view"), counter: $("file-counter"),
  previous: $("previous-button"), next: $("next-button"), content: $("figure-content"),
  art: $("figure-art"), artBox: $("art-box"), fallback: $("portrait-fallback"),
  name: $("figure-name"), game: $("figure-game"), type: $("figure-type"), element: $("figure-element"),
  characterProgress: $("character-progress"), vehicleProgress: $("vehicle-progress"),
  levelCurrent: $("current-level"), goldCurrent: $("current-gold"), gearCurrent: $("current-gearbits"),
  filename: $("selected-file"), message: $("preview-message"), settingsHeading: $("settings-heading"),
  levelGroup: $("level-group"), level: $("level-input"), goldGroup: $("gold-group"),
  currencyLabel: $("currency-label"), currency: $("gold-input"), maxLevel: $("max-level"),
  maxCurrency: $("max-currency"), settingsHint: $("settings-hint"), apply: $("apply-button"), toast: $("toast"),
};
const assetBase = new URL(location.pathname.includes("/web/") ? "../assets/" : "./assets/", location.href);
let catalog = {};
let vehicleTemplates = {};
let selectedFiles = [];
let currentIndex = 0;
let currentIsVehicle = false;
let toastTimer;

function bytesFromHex(hex) {
  return Uint8Array.from(hex.match(/.{2}/g) || [], (byte) => Number.parseInt(byte, 16));
}
function concatBytes(...parts) {
  const result = new Uint8Array(parts.reduce((size, part) => size + part.length, 0));
  let offset = 0;
  for (const part of parts) { result.set(part, offset); offset += part.length; }
  return result;
}
function hex(bytes) { return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join(""); }
function md5(message) {
  const bitLength = message.length * 8;
  const paddedLength = Math.ceil((message.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(message); padded[message.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, bitLength >>> 0, true);
  view.setUint32(paddedLength - 4, Math.floor(bitLength / 0x100000000), true);
  const shifts = [7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22,5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23,6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21];
  const constants = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 0x100000000) >>> 0);
  let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
  for (let offset = 0; offset < paddedLength; offset += 64) {
    const words = new Uint32Array(16);
    for (let i = 0; i < 16; i++) words[i] = view.getUint32(offset + i * 4, true);
    let a = a0, b = b0, c = c0, d = d0;
    for (let i = 0; i < 64; i++) {
      let f, g;
      if (i < 16) { f = (b & c) | (~b & d); g = i; }
      else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
      else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
      else { f = c ^ (b | ~d); g = (7 * i) % 16; }
      const sum = (a + f + constants[i] + words[g]) >>> 0;
      const rotated = ((sum << shifts[i]) | (sum >>> (32 - shifts[i]))) >>> 0;
      [a, d, c, b] = [d, c, b, (b + rotated) >>> 0];
    }
    a0 = (a0 + a) >>> 0; b0 = (b0 + b) >>> 0; c0 = (c0 + c) >>> 0; d0 = (d0 + d) >>> 0;
  }
  const digest = new Uint8Array(16), output = new DataView(digest.buffer);
  [a0, b0, c0, d0].forEach((word, i) => output.setUint32(i * 4, word, true));
  return digest;
}
const aesKeys = new Map();
async function aesKey(rawKey) {
  const keyHex = hex(rawKey);
  if (!aesKeys.has(keyHex)) aesKeys.set(keyHex, crypto.subtle.importKey("raw", rawKey, { name: "AES-CBC" }, false, ["encrypt", "decrypt"]));
  return aesKeys.get(keyHex);
}
async function aesBlock(block, keyBytes, decrypt) {
  const key = await aesKey(keyBytes);
  if (!decrypt) {
    const encrypted = await crypto.subtle.encrypt({ name: "AES-CBC", iv: new Uint8Array(16) }, key, block);
    return new Uint8Array(encrypted).slice(0, 16);
  }
  // Web Crypto exposes AES-CBC but not ECB. A chosen second CBC block creates
  // valid full-block padding, allowing the first block's raw AES inverse out.
  const padding = new Uint8Array(16).fill(16);
  const secondCipher = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-CBC", iv: block }, key, padding)).slice(0, 16);
  const decrypted = await crypto.subtle.decrypt({ name: "AES-CBC", iv: new Uint8Array(16) }, key, concatBytes(block, secondCipher));
  return new Uint8Array(decrypted).slice(0, 16);
}
async function transform(input, decrypt) {
  const output = input.slice();
  const header = input.slice(0, 32);
  for (let block = 8; block < 64; block++) {
    if (block % 4 === 3) continue;
    const offset = block * 16, data = input.slice(offset, offset + 16);
    if (data.every((byte) => byte === 0)) continue;
    const key = md5(concatBytes(header, Uint8Array.of(block), FORMAT_CONSTANT));
    output.set(await aesBlock(data, key, decrypt), offset);
  }
  return output;
}
function crc16(data) {
  let crc = 0xffff;
  for (const byte of data) {
    crc ^= byte << 8;
    for (let i = 0; i < 8; i++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return crc;
}
function crc1(data, block) {
  const offset = block * 16;
  return crc16(concatBytes(data.slice(offset, offset + 14), Uint8Array.of(5, 0)));
}
function crc2(data, block) {
  const at = block * 16;
  return crc16(concatBytes(Uint8Array.of(6, 1), data.slice(at + 2, at + 16), data.slice((block + 1) * 16, (block + 2) * 16), data.slice((block + 3) * 16, (block + 4) * 16), data.slice((block + 4) * 16, (block + 5) * 16)));
}
function newer(a, b) { return ((a - b) & 255) > 0 && ((a - b) & 255) < 128; }
function validA(data, block) {
  const at = block * 16, record = data.slice(at, at + 16);
  return record.some((byte) => byte !== 0) && new DataView(record.buffer, record.byteOffset, 16).getUint16(14, true) === crc1(data, block);
}
function validB(data, block) {
  const at = block * 16, record = data.slice(at, at + 16);
  return record.some((byte) => byte !== 0) && new DataView(record.buffer, record.byteOffset, 16).getUint16(0, true) === crc2(data, block);
}
function chooseValid(data, first, second, sequenceOffset, validator) {
  const a = validator(data, first), b = validator(data, second);
  if (a && b) return newer(data[first * 16 + sequenceOffset], data[second * 16 + sequenceOffset]) ? first : second;
  if (a) return first;
  if (b) return second;
  return null;
}
function active(data) {
  return [chooseValid(data, 8, 0x24, 9, validA), chooseValid(data, 0x11, 0x2d, 2, validB)];
}
function setU16(data, offset, value) { new DataView(data.buffer, data.byteOffset, data.byteLength).setUint16(offset, value, true); }
function setU32(data, offset, value) { new DataView(data.buffer, data.byteOffset, data.byteLength).setUint32(offset, value, true); }
function u16(data, offset) { return new DataView(data.buffer, data.byteOffset, data.byteLength).getUint16(offset, true); }
function u32(data, offset) { return new DataView(data.buffer, data.byteOffset, data.byteLength).getUint32(offset, true); }
function readFigureHeader(raw) {
  const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
  const toy = view.getUint16(0x10, true), variant = view.getUint16(0x1c, true);
  const id = toy.toString(16).toUpperCase().padStart(6, "0");
  const record = catalog[id] || null;
  return { toy, id, variant: variant.toString(16).toUpperCase().padStart(4, "0"), record };
}
function xpForLevel(level) {
  return [0, 0, 1000, 2200, 3800, 6000, 9000, 13000, 18000, 24000, 33000, 43000, 55000, 70000, 87000, 106000, 126000, 147000, 169000, 184000, 199535][level];
}
function splitXp(total) {
  const first = Math.min(total, 33000), rest = Math.max(0, total - 33000);
  const second = Math.min(rest, 63500);
  return [first, second, Math.max(0, rest - 63500)];
}
function levelFor(xp) {
  let level = 1;
  for (let n = 1; n <= 20; n++) if (xp >= xpForLevel(n)) level = n;
  return level;
}
async function inspect(raw, record) {
  const plain = await transform(raw, true), [a, b] = active(plain);
  if (a === null && b === null) return { plain, state: "uninitialized", level: 1, xp: 0, gold: 0, gearbits: 0 };
  if (a === null || b === null) throw new Error("Progress save is incomplete or damaged; no edit was made.");
  if (record?.type === "Vehicle") return { plain, state: "initialized", gearbits: u32(plain, b * 16 + 8) };
  const xp = plain[a * 16] + plain[a * 16 + 1] * 256 + plain[a * 16 + 2] * 65536 + u16(plain, b * 16 + 3) + u32(plain, b * 16 + 8);
  return { plain, state: "initialized", xp, level: levelFor(xp), gold: u16(plain, a * 16 + 3) };
}
function copyBlocks(destination, source, sourceBlock, destinationBlock, offsets) {
  for (const offset of offsets) destination.set(source.slice((sourceBlock + offset) * 16, (sourceBlock + offset + 1) * 16), (destinationBlock + offset) * 16);
}
function writeCrc1(data, block) { setU16(data, block * 16 + 14, crc1(data, block)); }
function writeCrc2(data, block) { setU16(data, block * 16, crc2(data, block)); }
async function editCharacter(raw, record, level, gold) {
  let plain = await transform(raw, true);
  let [activeA, activeB] = active(plain);
  if (activeA === null && activeB === null) {
    if (!INITIALIZABLE_TYPES.has(record.type)) throw new Error("Fresh-save initialization is only supported for recognized character figures.");
    for (const [block, data] of Object.entries(FRESH_CHARACTER_BLOCKS)) plain.set(bytesFromHex(data), Number(block) * 16);
    const [xp1, xp2, xp3] = splitXp(xpForLevel(level)), atA = 0x24 * 16, atB = 0x2d * 16;
    plain[atA] = xp1 & 255; plain[atA + 1] = (xp1 >>> 8) & 255; plain[atA + 2] = (xp1 >>> 16) & 255;
    setU16(plain, atA + 3, gold); plain[atA + 9] = 1;
    plain[atB + 2] = 1; setU16(plain, atB + 3, xp2); setU32(plain, atB + 8, xp3);
    writeCrc1(plain, 0x24); writeCrc2(plain, 0x2d);
  } else {
    if (activeA === null || activeB === null) throw new Error("Progress save is incomplete or damaged; no edit was made.");
    const destA = activeA === 8 ? 0x24 : 8, destB = activeB === 0x11 ? 0x2d : 0x11;
    const source = plain.slice();
    copyBlocks(plain, source, activeA, destA, [0, 1, 2, 4, 5, 6, 8]);
    copyBlocks(plain, source, activeB, destB, [0, 1, 3, 4]);
    const [xp1, xp2, xp3] = splitXp(xpForLevel(level)), atA = destA * 16, atB = destB * 16;
    plain[atA] = xp1 & 255; plain[atA + 1] = (xp1 >>> 8) & 255; plain[atA + 2] = (xp1 >>> 16) & 255;
    setU16(plain, atA + 3, gold); plain[atA + 9] = (source[activeA * 16 + 9] + 1) & 255; writeCrc1(plain, destA);
    plain[atB + 2] = (source[activeB * 16 + 2] + 1) & 255; setU16(plain, atB + 3, xp2); setU32(plain, atB + 8, xp3); writeCrc2(plain, destB);
  }
  const encoded = await transform(plain, false), check = await inspect(encoded, record);
  if (check.state !== "initialized" || check.level !== level || check.gold !== gold) throw new Error("Post-write validation failed; no download was created.");
  return encoded;
}
async function editVehicle(raw, record, gearbits) {
  let plain = await transform(raw, true);
  let [activeA, activeB] = active(plain);
  if (activeA === null && activeB === null) {
    const template = vehicleTemplates[readFigureHeader(raw).id];
    if (!template) throw new Error("No captured fresh-save template is available for this vehicle model.");
    for (const block of Object.keys(template)) if (plain.slice(Number.parseInt(block, 16) * 16, (Number.parseInt(block, 16) + 1) * 16).some((byte) => byte !== 0)) throw new Error("Vehicle has non-empty invalid progress data; refusing to initialize it.");
    for (const [block, data] of Object.entries(template)) plain.set(bytesFromHex(data), Number.parseInt(block, 16) * 16);
    for (const block of [0x11, 0x2d]) { setU32(plain, block * 16 + 8, gearbits); writeCrc2(plain, block); }
  } else {
    if (activeA === null || activeB === null) throw new Error("Vehicle progress save is incomplete or damaged; no edit was made.");
    const destination = activeB === 0x11 ? 0x2d : 0x11, source = plain.slice();
    copyBlocks(plain, source, activeB, destination, [0, 1, 3, 4]);
    const offset = destination * 16;
    plain[offset + 2] = (source[activeB * 16 + 2] + 1) & 255;
    setU32(plain, offset + 8, gearbits); writeCrc2(plain, destination);
  }
  const encoded = await transform(plain, false), check = await inspect(encoded, record);
  if (check.state !== "initialized" || check.gearbits !== gearbits) throw new Error("Vehicle Gearbits validation failed; no download was created.");
  return encoded;
}
function detailName(header) {
  if (!header.record) return `Unknown figure (ID ${header.id})`;
  return header.record.variants?.[header.variant]?.name || header.record.name;
}
async function readDirectory(handle, parent = "") {
  const files = [];
  for await (const [name, entry] of handle.entries()) {
    if (entry.kind === "directory") files.push(...await readDirectory(entry, `${parent}${name}/`));
    else if (/\.(sky|dump)$/i.test(name)) {
      const file = await entry.getFile();
      Object.defineProperty(file, "relativePath", { value: `${parent}${name}` });
      files.push(file);
    }
  }
  return files;
}
function portraitPath(header) {
  if (!header.record) return null;
  const portrait = header.record.variants?.[header.variant]?.image || header.record.image;
  return portrait ? new URL(`portraits/${encodeURIComponent(portrait)}`, assetBase).href : null;
}
function setAccent(color) {
  document.documentElement.style.setProperty("--accent", color || "#91a0ad");
}
function showToast(message, duration = 4500) {
  clearTimeout(toastTimer); ui.toast.textContent = message; ui.toast.classList.add("visible");
  toastTimer = setTimeout(() => ui.toast.classList.remove("visible"), duration);
}
async function loadCurrent() {
  if (!selectedFiles.length) return;
  const file = selectedFiles[currentIndex];
  ui.counter.textContent = `${currentIndex + 1} / ${selectedFiles.length}`;
  ui.filename.textContent = file.relativePath || file.webkitRelativePath || file.name;
  ui.message.textContent = "Reading figure…";
  ui.art.hidden = true; ui.fallback.hidden = true;
  try {
    const raw = new Uint8Array(await file.arrayBuffer());
    if (raw.length !== 1024) throw new Error(`Expected a 1,024-byte figure file; found ${raw.length.toLocaleString()} bytes.`);
    const header = readFigureHeader(raw), record = header.record, data = await inspect(raw, record);
    currentIsVehicle = record?.type === "Vehicle";
    ui.name.textContent = detailName(header);
    ui.game.textContent = record?.game || "Unknown game";
    ui.type.textContent = record?.type || "Unknown type";
    const element = record?.element || "Unknown";
    ui.element.textContent = `${element} element`;
    setAccent(({ Magic:"#a879ff",Water:"#48aaff",Fire:"#ff765e",Life:"#70d65f",Undead:"#a89cff",Earth:"#e6ad5b",Air:"#51d4d0",Tech:"#f28c38",Light:"#ffe16a",Dark:"#c19aff" })[element] || "#91a0ad");
    ui.characterProgress.hidden = currentIsVehicle;
    ui.vehicleProgress.hidden = !currentIsVehicle;
    ui.levelGroup.hidden = currentIsVehicle;
    ui.currencyLabel.textContent = currentIsVehicle ? "Gearbits" : "Gold";
    ui.goldGroup.querySelector("input").max = currentIsVehicle ? MAX_GEARBITS : MAX_GOLD;
    ui.maxCurrency.textContent = currentIsVehicle ? "Set max Gearbits" : "Set max gold";
    ui.maxCurrency.onclick = () => { ui.currency.value = currentIsVehicle ? MAX_GEARBITS : MAX_GOLD; };
    ui.settingsHeading.textContent = currentIsVehicle ? "Vehicle settings" : "Batch settings";
    ui.settingsHint.textContent = currentIsVehicle
      ? `Starting Gearbits value: 0. Maximum: ${MAX_GEARBITS.toLocaleString()}. The same value will be applied to every selected vehicle.`
      : "Starting values: Level 1 and 0 gold. The same values will be applied to every selected Skylander.";
    if (currentIsVehicle) ui.gearCurrent.textContent = data.state === "uninitialized" ? "0" : data.gearbits.toLocaleString();
    else { ui.levelCurrent.textContent = data.level.toLocaleString(); ui.goldCurrent.textContent = data.gold.toLocaleString(); }
    const picture = portraitPath(header);
    if (picture) {
      ui.art.onload = () => {
        ui.art.hidden = false; ui.fallback.hidden = true;
        ui.content.classList.toggle("landscape", ui.art.naturalWidth > ui.art.naturalHeight);
        ui.content.classList.toggle("portrait", ui.art.naturalWidth <= ui.art.naturalHeight);
      };
      ui.art.onerror = () => { ui.art.hidden = true; ui.fallback.hidden = false; };
      ui.art.alt = `${detailName(header)} portrait`;
      ui.art.src = picture;
    } else { ui.fallback.hidden = false; ui.fallback.textContent = "Portrait unavailable"; }
    ui.message.textContent = data.state === "uninitialized"
      ? "Uninitialized save. Supported figures will be initialized when the edited copy is created."
      : "Current progress loaded. Batch input fields start at their minimum values.";
    ui.apply.disabled = false;
    ui.previous.disabled = selectedFiles.length < 2;
    ui.next.disabled = selectedFiles.length < 2;
  } catch (error) {
    ui.name.textContent = "Unable to read figure"; ui.game.textContent = "Figure data unavailable";
    ui.type.textContent = ""; ui.element.textContent = ""; ui.message.textContent = error.message;
    ui.apply.disabled = true; ui.fallback.hidden = false; ui.fallback.textContent = "Preview unavailable";
  }
}
function addSelection(fileList) {
  selectedFiles = Array.from(fileList).filter((file) => /\.(sky|dump)$/i.test(file.name));
  currentIndex = 0;
  ui.level.value = "1"; ui.currency.value = "0"; ui.currency.max = String(MAX_GOLD);
  ui.currencyLabel.textContent = "Gold"; ui.maxCurrency.textContent = "Set max gold";
  ui.maxCurrency.onclick = () => { ui.currency.value = MAX_GOLD; };
  ui.empty.hidden = selectedFiles.length > 0;
  ui.view.hidden = selectedFiles.length === 0;
  ui.apply.disabled = selectedFiles.length === 0;
  ui.filePicker.value = ""; ui.folderPicker.value = "";
  if (!selectedFiles.length) { showToast("No .sky or .dump files were found in that selection."); return; }
  loadCurrent();
}
function validateInput(value, min, max, label) {
  const number = Number(value);
  if (!Number.isInteger(number) || number < min || number > max) throw new Error(`${label} must be a whole number from ${min.toLocaleString()} to ${max.toLocaleString()}.`);
  return number;
}
function copyName(file, used) {
  const name = file.name, dot = name.lastIndexOf("."), stem = dot > 0 ? name.slice(0, dot) : name, ext = dot > 0 ? name.slice(dot) : "";
  let candidate = `${stem}_copy${ext}`, suffix = 2;
  while (used.has(candidate.toLowerCase())) candidate = `${stem}_copy_${suffix++}${ext}`;
  used.add(candidate.toLowerCase()); return candidate;
}
function download(data, name) {
  const url = URL.createObjectURL(new Blob([data], { type: "application/octet-stream" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = name; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
async function applyBatch() {
  if (!selectedFiles.length) return;
  ui.apply.disabled = true; ui.apply.textContent = "Preparing edited copies…";
  try {
    const rawFiles = [];
    for (const file of selectedFiles) {
      const raw = new Uint8Array(await file.arrayBuffer());
      if (raw.length !== 1024) throw new Error(`${file.name}: expected a 1,024-byte figure file.`);
      const header = readFigureHeader(raw);
      if (!header.record) throw new Error(`${file.name}: unknown figure ID ${header.id}; editing is limited to catalogued figures.`);
      rawFiles.push({ raw, header, file });
    }
    const firstHeader = rawFiles[0].header;
    currentIsVehicle = firstHeader.record?.type === "Vehicle";
    if (rawFiles.some(({ header }) => (header.record.type === "Vehicle") !== currentIsVehicle)) throw new Error("Select Skylanders and vehicles in separate batches.");
    const level = currentIsVehicle ? 1 : validateInput(ui.level.value, 1, 20, "Level");
    const currency = currentIsVehicle ? validateInput(ui.currency.value, 0, MAX_GEARBITS, "Gearbits") : validateInput(ui.currency.value, 0, MAX_GOLD, "Gold");
    const used = new Set();
    const outputs = [];
    for (const { raw, header, file } of rawFiles) {
      const edited = currentIsVehicle
        ? await editVehicle(raw, header.record, currency)
        : await editCharacter(raw, header.record, level, currency);
      outputs.push({ data: edited, name: copyName(file, used) });
    }
    for (const output of outputs) {
      download(output.data, output.name);
      await new Promise((resolve) => setTimeout(resolve, 180));
    }
    showToast(`Created ${selectedFiles.length} validated edited ${selectedFiles.length === 1 ? "copy" : "copies"}. Check your browser's downloads.`);
  } catch (error) { showToast(error.message, 8000); }
  finally { ui.apply.disabled = false; ui.apply.textContent = "Download edited copies"; }
}
async function loadAssets() {
  const [catalogResponse, templatesResponse] = await Promise.all([
    fetch(new URL("skylanders_db.json", assetBase)), fetch(new URL("vehicle_fresh_templates.json", assetBase)),
  ]);
  if (!catalogResponse.ok || !templatesResponse.ok) throw new Error("Could not load the figure catalog or vehicle templates.");
  [catalog, vehicleTemplates] = await Promise.all([catalogResponse.json(), templatesResponse.json()]);
}
ui.filePicker.addEventListener("change", (event) => addSelection(event.target.files));
ui.folderPicker.addEventListener("change", (event) => addSelection(event.target.files));
ui.chooseFolder.addEventListener("click", async () => {
  if (!window.showDirectoryPicker) { ui.folderPicker.click(); return; }
  try {
    const directory = await window.showDirectoryPicker({ mode: "read" });
    addSelection(await readDirectory(directory));
  } catch (error) {
    if (error.name !== "AbortError") showToast(`Could not read that folder: ${error.message}`);
  }
});
const dropTarget = document.querySelector(".preview-panel");
dropTarget.addEventListener("dragover", (event) => { event.preventDefault(); dropTarget.classList.add("drag-over"); });
dropTarget.addEventListener("dragleave", (event) => { if (!dropTarget.contains(event.relatedTarget)) dropTarget.classList.remove("drag-over"); });
dropTarget.addEventListener("drop", (event) => { event.preventDefault(); dropTarget.classList.remove("drag-over"); addSelection(event.dataTransfer.files); });
ui.clear.addEventListener("click", () => {
  selectedFiles = []; currentIndex = 0; ui.empty.hidden = false; ui.view.hidden = true; ui.apply.disabled = true;
  ui.level.value = "1"; ui.currency.value = "0"; setAccent("#48aaff");
  ui.currency.max = String(MAX_GOLD); ui.currencyLabel.textContent = "Gold";
  ui.maxCurrency.textContent = "Set max gold"; ui.maxCurrency.onclick = () => { ui.currency.value = MAX_GOLD; };
  ui.levelGroup.hidden = false; ui.settingsHeading.textContent = "Batch settings";
  ui.settingsHint.textContent = "Starting values: Level 1 and 0 gold. Set the values you want applied to the selection.";
});
ui.previous.addEventListener("click", () => { currentIndex = (currentIndex - 1 + selectedFiles.length) % selectedFiles.length; loadCurrent(); });
ui.next.addEventListener("click", () => { currentIndex = (currentIndex + 1) % selectedFiles.length; loadCurrent(); });
ui.maxLevel.addEventListener("click", () => { ui.level.value = "20"; });
ui.apply.addEventListener("click", applyBatch);
window.addEventListener("keydown", (event) => {
  if (event.target instanceof HTMLInputElement) return;
  if (event.key === "ArrowLeft" && selectedFiles.length > 1) ui.previous.click();
  if (event.key === "ArrowRight" && selectedFiles.length > 1) ui.next.click();
});
loadAssets().catch((error) => showToast(`${error.message} Serve the project or the deployed site over HTTPS; opening the HTML file directly is not supported.`, 9000));
