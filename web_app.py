from flask import Flask, jsonify, request, render_template, send_from_directory
import os
import google.generativeai as genai
from file_system_recovery_tool import VirtualDisk, BTree, LRUCache

app = Flask(__name__, static_folder='static', template_folder='templates')

# Global instances for the simulation
disk = VirtualDisk()
btree = BTree()
lru = LRUCache(capacity=4)
bench_results = []

# Replace with the API key provided by the user via environment variable or placeholder
API_KEY = os.environ.get("GEMINI_API_KEY", "")
if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    return jsonify({
        "sectors": disk.sectors,
        "files": disk.files,
        "journal": disk.journal,
        "btree_keys": btree.traverse(),
        "lru_snapshot": [k for k, v in lru.snapshot()],
        "benchmarks": bench_results
    })

@app.route('/api/write', methods=['POST'])
def write_file():
    data = request.json
    name = data.get("name", f"file_{len(disk.files)}")
    ftype = data.get("ftype", "pdf")
    entry, err = disk.write_file(name, ftype)
    if err:
        return jsonify({"error": err}), 400
    
    btree.insert(name, entry)
    lru.put(f"{name}.{ftype}", entry)
    return jsonify({"success": True, "entry": entry})

@app.route('/api/crash', methods=['POST'])
def simulate_crash():
    data = request.json
    mode = data.get("mode", "random")
    events = disk.simulate_crash(mode)
    return jsonify({"events": events})

@app.route('/api/reset', methods=['POST'])
def reset_disk():
    global disk, btree, lru, bench_results
    disk.reset()
    btree = BTree()
    lru = LRUCache(capacity=4)
    bench_results = []
    return jsonify({"success": True})

@app.route('/api/recover/signatures', methods=['POST'])
def scan_signatures():
    results = disk.scan_signatures()
    # Format results to be JSON serializable
    formatted = [{"file": f, "signature": sig, "sector": sector} for f, sig, sector in results]
    return jsonify({"results": formatted})

@app.route('/api/recover/journal', methods=['POST'])
def recover_journal():
    recovered, failed = disk.recover_journal()
    return jsonify({"recovered": recovered, "failed": failed})

@app.route('/api/recover/all', methods=['POST'])
def recover_all():
    recovered, lost = disk.recover_all()
    return jsonify({"recovered": recovered, "lost": lost})

@app.route('/api/benchmark', methods=['POST'])
def run_benchmark():
    data = request.json
    mode = data.get("mode", "none")
    read_spd, write_spd = disk.benchmark(mode)
    bench_results.append({"mode": mode, "read": read_spd, "write": write_spd})
    
    if mode == "both":
        compacted = disk.defragment()
        return jsonify({"read": read_spd, "write": write_spd, "compacted": compacted})
    
    return jsonify({"read": read_spd, "write": write_spd})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data.get("prompt", "")
    if not model:
        return jsonify({"reply": "AI is not configured. Please provide an API key."})
    try:
        response = model.generate_content(
            f"You are a helpful assistant for a File System Recovery & Optimization tool. Keep your answers concise and relevant to OS file systems. User says: {prompt}"
        )
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"Error calling AI: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
