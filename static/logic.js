class BTreeNode {
    constructor(leaf = true) {
        this.keys = [];
        this.values = [];
        this.children = [];
        this.leaf = leaf;
    }
}

class BTree {
    constructor(t = 2) {
        this.root = new BTreeNode();
        this.t = t;
    }

    insert(key, value) {
        let r = this.root;
        if (r.keys.length === 2 * this.t - 1) {
            let s = new BTreeNode(false);
            s.children.push(this.root);
            this._splitChild(s, 0);
            this.root = s;
        }
        this._insertNonFull(this.root, key, value);
    }

    _insertNonFull(node, key, value) {
        let i = node.keys.length - 1;
        if (node.leaf) {
            node.keys.push(null);
            node.values.push(null);
            while (i >= 0 && key < node.keys[i]) {
                node.keys[i + 1] = node.keys[i];
                node.values[i + 1] = node.values[i];
                i--;
            }
            node.keys[i + 1] = key;
            node.values[i + 1] = value;
        } else {
            while (i >= 0 && key < node.keys[i]) {
                i--;
            }
            i++;
            if (node.children[i].keys.length === 2 * this.t - 1) {
                this._splitChild(node, i);
                if (key > node.keys[i]) {
                    i++;
                }
            }
            this._insertNonFull(node.children[i], key, value);
        }
    }

    _splitChild(parent, i) {
        let t = this.t;
        let y = parent.children[i];
        let z = new BTreeNode(y.leaf);
        parent.keys.splice(i, 0, y.keys[t - 1]);
        parent.values.splice(i, 0, y.values[t - 1]);
        parent.children.splice(i + 1, 0, z);
        z.keys = y.keys.slice(t);
        z.values = y.values.slice(t);
        y.keys = y.keys.slice(0, t - 1);
        y.values = y.values.slice(0, t - 1);
        if (!y.leaf) {
            z.children = y.children.slice(t);
            y.children = y.children.slice(0, t);
        }
    }

    search(key, node = this.root) {
        let i = 0;
        while (i < node.keys.length && key > node.keys[i]) {
            i++;
        }
        if (i < node.keys.length && key === node.keys[i]) {
            return node.values[i];
        }
        if (node.leaf) {
            return null;
        }
        return this.search(key, node.children[i]);
    }

    traverse(node = this.root, result = []) {
        for (let i = 0; i < node.keys.length; i++) {
            if (!node.leaf) {
                this.traverse(node.children[i], result);
            }
            result.push(node.keys[i]);
        }
        if (!node.leaf) {
            this.traverse(node.children[node.children.length - 1], result);
        }
        return result;
    }
}

class LRUCache {
    constructor(capacity = 4) {
        this.capacity = capacity;
        this.cache = new Map();
    }

    get(key) {
        if (!this.cache.has(key)) return null;
        let val = this.cache.get(key);
        this.cache.delete(key);
        this.cache.set(key, val);
        return val;
    }

    put(key, value) {
        if (this.cache.has(key)) {
            this.cache.delete(key);
        }
        this.cache.set(key, value);
        if (this.cache.size > this.capacity) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
    }

    snapshot() {
        return Array.from(this.cache.entries()).reverse();
    }
}

const SECTOR_COUNT = 512;
const SECTOR_SIZE = 128;
const STATUS_FREE = 0;
const STATUS_USED = 1;
const STATUS_CORRUPTED = 2;
const STATUS_RECOVERED = 3;
const STATUS_BAD = 4;

const FILE_SIGNATURES = {
    "pdf": "25504446",
    "jpg": "FFD8FFE0",
    "txt": "EFBBBF00",
    "mp4": "00000018",
    "docx": "504B0304"
};

function generateHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash;
    }
    return Math.abs(hash).toString(16).substring(0, 8).toUpperCase();
}

function randInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

class VirtualDisk {
    constructor() {
        this.sectors = Array(SECTOR_COUNT).fill(STATUS_FREE);
        this.files = [];
        this.journal = [];
    }

    free_sectors() {
        let free = [];
        for (let i = 0; i < this.sectors.length; i++) {
            if (this.sectors[i] === STATUS_FREE) free.push(i);
        }
        return free;
    }

    allocate(count) {
        let free = this.free_sectors();
        if (free.length < count) return null;
        let start = free[randInt(0, Math.max(0, free.length - count))];
        let allocated = [];
        for (let i = start; i < Math.min(start + count, SECTOR_COUNT); i++) {
            allocated.push(i);
            this.sectors[i] = STATUS_USED;
        }
        return allocated;
    }

    write_file(name, ftype) {
        const sizes = { "pdf": [80, 400], "jpg": [120, 800], "txt": [4, 50], "mp4": [2000, 8000], "docx": [40, 200] };
        const bounds = sizes[ftype] || [50, 300];
        const size_kb = randInt(bounds[0], bounds[1]);
        const sector_count = Math.max(2, Math.floor(size_kb / (SECTOR_SIZE / 1024 + 1)));
        
        let allocated = this.allocate(sector_count);
        if (!allocated) return { err: "Not enough free sectors" };
        
        let checksum = generateHash(`${name}${ftype}${Date.now()}`);
        let entry = {
            name, ftype, size_kb, sectors: allocated, status: "ok", checksum
        };
        this.files.push(entry);
        
        this.journal.push({
            ts: new Date().toLocaleTimeString(),
            event: "WRITE",
            filename: `${name}.${ftype}`,
            sectors: `${allocated[0]}-${allocated[allocated.length - 1]}`,
            checksum,
            data: { ...entry }
        });
        
        return { entry };
    }

    simulate_crash(mode = "random") {
        let events = [];
        if (mode === "random") {
            let n = randInt(10, 40);
            let corrupted = 0;
            for (let i = 0; i < n; i++) {
                let idx = randInt(0, SECTOR_COUNT - 1);
                if (this.sectors[idx] === STATUS_USED) {
                    this.sectors[idx] = STATUS_CORRUPTED;
                    corrupted++;
                }
            }
            this.files.forEach(f => {
                if (f.sectors.some(s => this.sectors[s] === STATUS_CORRUPTED)) {
                    if (f.status === "ok") f.status = "corrupt";
                }
            });
            events.push(`Random crash: ${corrupted} sectors corrupted`);
        } else if (mode === "power") {
            if (this.files.length === 0) return ["No files to corrupt"];
            let victim = this.files[randInt(0, this.files.length - 1)];
            let half = Math.floor(victim.sectors.length / 2);
            for (let i = 0; i < half; i++) {
                this.sectors[victim.sectors[i]] = STATUS_CORRUPTED;
            }
            victim.status = "corrupt";
            events.push(`Power failure: partial write of ${victim.name}.${victim.ftype}`);
        } else if (mode === "bad") {
            let n = randInt(5, 20);
            let marked = 0;
            for (let i = 0; i < n; i++) {
                let idx = randInt(0, SECTOR_COUNT - 1);
                if (this.sectors[idx] === STATUS_FREE) {
                    this.sectors[idx] = STATUS_BAD;
                    marked++;
                }
            }
            events.push(`Bad blocks: ${marked} sectors marked unreadable`);
        }
        this.journal.push({
            ts: new Date().toLocaleTimeString(),
            event: "CRASH", mode, description: events[0]
        });
        return events;
    }

    reset() {
        this.sectors = Array(SECTOR_COUNT).fill(STATUS_FREE);
        this.files = [];
        this.journal = [];
    }

    scan_signatures() {
        let results = [];
        this.files.forEach(f => {
            if (f.status === "corrupt") {
                let sig = FILE_SIGNATURES[f.ftype] || "DEADBEEF";
                results.push([f, sig, f.sectors[0]]);
            }
        });
        return results;
    }

    recover_journal() {
        let recovered = [], failed = [];
        this.files.forEach(f => {
            if (f.status !== "corrupt") return;
            let j_entry = this.journal.find(j => j.event === "WRITE" && j.filename === `${f.name}.${f.ftype}`);
            if (j_entry && Math.random() > 0.25) {
                f.status = "recovered";
                f.sectors.forEach(s => {
                    if (this.sectors[s] === STATUS_CORRUPTED) this.sectors[s] = STATUS_RECOVERED;
                });
                recovered.push(f);
            } else {
                failed.push(f);
            }
        });
        return { recovered, failed };
    }

    recover_all() {
        let recovered = [], lost = [];
        this.files.forEach(f => {
            if (f.status !== "corrupt") return;
            if (Math.random() > 0.15) {
                f.status = "recovered";
                f.sectors.forEach(s => {
                    if (this.sectors[s] === STATUS_CORRUPTED) this.sectors[s] = STATUS_RECOVERED;
                });
                recovered.push(f);
            } else {
                f.status = "lost";
                lost.push(f);
            }
        });
        return { recovered, lost };
    }

    benchmark(optimization = "none") {
        let base_read = 40 + Math.random() * 15;
        let base_write = 35 + Math.random() * 13;
        const multipliers = {
            "none": [1.0, 1.0],
            "btree": [2.8, 1.4],
            "lru": [3.5, 1.2],
            "both": [5.2, 2.1]
        };
        let [rm, wm] = multipliers[optimization] || [1.0, 1.0];
        return { read: (base_read * rm).toFixed(1), write: (base_write * wm).toFixed(1) };
    }

    defragment() {
        let used_files = this.files.filter(f => f.status === "ok" || f.status === "recovered");
        this.sectors = Array(SECTOR_COUNT).fill(STATUS_FREE);
        let ptr = 0;
        used_files.forEach(f => {
            let count = f.sectors.length;
            f.sectors = Array.from({length: count}, (_, i) => ptr + i);
            f.sectors.forEach(s => this.sectors[s] = STATUS_USED);
            ptr += count;
        });
        return used_files.length;
    }
}

// Global instances for the frontend logic
window.fsDisk = new VirtualDisk();
window.fsBTree = new BTree();
window.fsLRU = new LRUCache();
window.fsBenchmarks = [];
