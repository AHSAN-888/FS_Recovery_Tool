const { useState, useEffect, useRef } = React;

const STATUS_COLORS = {
    0: 'bg-free',
    1: 'bg-used',
    2: 'bg-corrupted',
    3: 'bg-recovered',
    4: 'bg-bad'
};

function App() {
    const [state, setState] = useState({
        sectors: Array(SECTOR_COUNT).fill(0),
        files: [],
        journal: [],
        btree_keys: [],
        lru_snapshot: [],
        benchmarks: []
    });
    const [logs, setLogs] = useState(["System initialized in pure Client-Side mode."]);
    const [statusText, setStatusText] = useState("System nominal — disk mounted");
    const [statusColor, setStatusColor] = useState("green");

    const refreshState = () => {
        setState({
            sectors: [...window.fsDisk.sectors],
            files: [...window.fsDisk.files],
            journal: [...window.fsDisk.journal],
            btree_keys: window.fsBTree.traverse(),
            lru_snapshot: window.fsLRU.snapshot().map(e => e[0]),
            benchmarks: [...window.fsBenchmarks]
        });
    };

    useEffect(() => {
        refreshState();
    }, []);

    const addLog = (msg) => {
        setLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    };

    const handleAction = async (action, payload) => {
        try {
            let res = {};
            if (action === 'write') {
                const { name, ftype } = payload;
                const { entry, err } = window.fsDisk.write_file(name, ftype);
                if (err) res.error = err;
                else {
                    window.fsBTree.insert(name, entry);
                    window.fsLRU.put(`${name}.${ftype}`, entry);
                    res.entry = entry;
                }
            } else if (action === 'crash') {
                res.events = window.fsDisk.simulate_crash(payload.mode);
            } else if (action === 'reset') {
                window.fsDisk.reset();
                window.fsBTree = new BTree();
                window.fsLRU = new LRUCache();
                window.fsBenchmarks = [];
            } else if (action === 'recover/signatures') {
                res.results = window.fsDisk.scan_signatures();
            } else if (action === 'recover/journal') {
                res = window.fsDisk.recover_journal();
            } else if (action === 'recover/all') {
                res = window.fsDisk.recover_all();
            } else if (action === 'benchmark') {
                const speeds = window.fsDisk.benchmark(payload.mode);
                window.fsBenchmarks.push({ mode: payload.mode, ...speeds });
                res = { ...speeds };
                if (payload.mode === 'both') {
                    res.compacted = window.fsDisk.defragment();
                }
            }
            refreshState();
            return res;
        } catch (e) {
            console.error(e);
            return { error: e.message };
        }
    };

    return (
        <div className="app-container fade-in">
            <header className="glass-panel">
                <div className="header-left">
                    <div className="status-indicator">
                        <span className={`dot ${statusColor}`}></span>
                    </div>
                    <div>
                        <h1>FS Recovery Tool <span style={{fontSize: "0.5em", verticalAlign: "top", background: "rgba(139, 92, 246, 0.2)", color: "#c4b5fd", padding: "2px 6px", borderRadius: "4px"}}>React Client-Side</span></h1>
                        <p className="subtitle">CSE-316 CA2 | Advanced File System Simulator</p>
                    </div>
                </div>
                <div className="header-right">
                    <p className={`status-text text-${statusColor}`}>{statusText}</p>
                </div>
            </header>

            <div className="main-content">
                <Controls 
                    onAction={handleAction} 
                    addLog={addLog} 
                    setStatus={(text, color) => { setStatusText(text); setStatusColor(color); }}
                    files={state.files}
                />
                
                <main className="workspace">
                    <DiskPanel sectors={state.sectors} files={state.files} />
                    
                    <div className="bottom-panels">
                        <FileTable files={state.files} />
                        <LogPanel logs={logs} />
                    </div>


                </main>
            </div>
            

        </div>
    );
}

function Controls({ onAction, addLog, setStatus, files }) {
    const [filename, setFilename] = useState("report");
    const [ftype, setFtype] = useState("pdf");

    const write = async () => {
        const data = await onAction('write', { name: filename, ftype });
        if (data.error) {
            addLog(`ERROR: ${data.error}`);
        } else {
            addLog(`WRITE OK: ${filename}.${ftype}`);
            setStatus("System nominal — disk mounted", "green");
        }
    };

    const crash = async (mode) => {
        const data = await onAction('crash', { mode });
        if (data.events) {
            data.events.forEach(e => addLog(`CRASH: ${e}`));
        }
        setStatus("ALERT: Disk crash detected — run recovery engine", "red");
    };

    const reset = async () => {
        await onAction('reset');
        addLog("Disk reset complete.");
        setStatus("System nominal — disk mounted", "green");
    };

    const recoverSigs = async () => {
        const data = await onAction('recover/signatures');
        if (data.results) {
            addLog(`Signature scan complete. Found ${data.results.length} signatures.`);
        }
    };

    const recoverJ = async () => {
        const data = await onAction('recover/journal');
        addLog(`Journal recovery: ${data.recovered?.length || 0} restored.`);
    };

    const recoverAll = async () => {
        setStatus("Recovering files...", "amber");
        const data = await onAction('recover/all');
        addLog(`Recover All: ${data.recovered?.length || 0} restored, ${data.lost?.length || 0} lost.`);
        setStatus("Recovery complete", "green");
    };

    const bench = async (mode) => {
        const data = await onAction('benchmark', { mode });
        addLog(`Benchmark [${mode}]: Read ${data.read} MB/s, Write ${data.write} MB/s`);
        if (data.compacted !== undefined) {
            addLog(`Defrag complete: ${data.compacted} files compacted.`);
        }
    };

    const corruptCount = files.filter(f => f.status === 'corrupt').length;
    const recoveredCount = files.filter(f => f.status === 'recovered').length;

    return (
        <aside className="controls-panel">
            <div className="glass-panel section-panel">
                <h2>Module 1: Simulator</h2>
                <div className="control-group">
                    <label>Filename</label>
                    <input type="text" value={filename} onChange={e => setFilename(e.target.value)} />
                </div>
                <div className="control-group">
                    <label>Type</label>
                    <select value={ftype} onChange={e => setFtype(e.target.value)}>
                        <option value="pdf">PDF</option>
                        <option value="jpg">JPG</option>
                        <option value="txt">TXT</option>
                        <option value="mp4">MP4</option>
                        <option value="docx">DOCX</option>
                    </select>
                </div>
                <button className="btn primary full-width" onClick={write}>Write File</button>
                
                <div className="divider"></div>
                
                <div className="button-grid">
                    <button className="btn danger" onClick={() => crash('random')}>Rand Crash</button>
                    <button className="btn danger" onClick={() => crash('power')}>Power Fail</button>
                    <button className="btn warning" onClick={() => crash('bad')}>Bad Blocks</button>
                    <button className="btn outline" onClick={reset}>Reset Disk</button>
                </div>
            </div>

            <div className="glass-panel section-panel">
                <h2>Module 2: Recovery</h2>
                <div className="recovery-stats">
                    <div className="stat-box">
                        <span className="stat-label">Corrupt</span>
                        <span className="stat-value text-red">{corruptCount}</span>
                    </div>
                    <div className="stat-box">
                        <span className="stat-label">Recovered</span>
                        <span className="stat-value text-green">{recoveredCount}</span>
                    </div>
                </div>
                <div className="button-grid" style={{marginTop: '10px'}}>
                    <button className="btn secondary" onClick={recoverSigs}>Sig Scan</button>
                    <button className="btn secondary" onClick={recoverJ}>Journal Rec.</button>
                    <button className="btn success full-width" onClick={recoverAll}>Recover All</button>
                </div>
            </div>


        </aside>
    );
}

function DiskPanel({ sectors }) {
    const used = sectors.filter(s => s === 1).length;
    const corrupt = sectors.filter(s => s === 2).length;
    const recovered = sectors.filter(s => s === 3).length;
    const bad = sectors.filter(s => s === 4).length;
    
    const totalUsed = used + corrupt + recovered + bad;
    const usagePct = Math.round((totalUsed / SECTOR_COUNT) * 100);
    const corruptPct = Math.round((corrupt / SECTOR_COUNT) * 100);

    return (
        <div className="glass-panel disk-panel">
            <div className="panel-header">
                <h2>Virtual Disk Map (512 Sectors)</h2>
                <div className="legend">
                    <span className="legend-item"><span className="dot bg-free"></span> Free</span>
                    <span className="legend-item"><span className="dot bg-used"></span> Used</span>
                    <span className="legend-item"><span className="dot bg-corrupted"></span> Corrupt</span>
                    <span className="legend-item"><span className="dot bg-recovered"></span> Recovered</span>
                    <span className="legend-item"><span className="dot bg-bad"></span> Bad Block</span>
                </div>
            </div>
            <div className="disk-grid">
                {sectors.map((s, i) => (
                    <div key={i} className={`sector ${STATUS_COLORS[s]}`} title={`Sector ${i}`}></div>
                ))}
            </div>
            <div className="progress-bars">
                <div className="progress-bar-container">
                    <label>Storage <span>{usagePct}%</span></label>
                    <div className="progress-track"><div className="progress-fill bg-used" style={{width: `${usagePct}%`}}></div></div>
                </div>
                <div className="progress-bar-container">
                    <label>Corruption <span>{corruptPct}%</span></label>
                    <div className="progress-track"><div className="progress-fill bg-corrupted" style={{width: `${corruptPct}%`}}></div></div>
                </div>
            </div>
        </div>
    );
}

function FileTable({ files }) {
    const getStatusColor = (status) => {
        if (status === 'ok') return 'text-green';
        if (status === 'corrupt') return 'text-red';
        if (status === 'recovered') return 'text-blue';
        return 'text-amber';
    };

    return (
        <div className="glass-panel table-panel">
            <h2>File Allocation Table</h2>
            <div className="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Type</th>
                            <th>Size</th>
                            <th>Sectors</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {files.map((f, i) => (
                            <tr key={i}>
                                <td>{f.name}</td>
                                <td>{f.ftype.toUpperCase()}</td>
                                <td>{f.size_kb}KB</td>
                                <td>{f.sectors && f.sectors.length > 0 ? `${f.sectors[0]}-${f.sectors[f.sectors.length-1]}` : '-'}</td>
                                <td className={getStatusColor(f.status)}>{f.status.toUpperCase()}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function LogPanel({ logs }) {
    const logEndRef = useRef(null);
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    return (
        <div className="glass-panel log-panel">
            <h2>System Logs</h2>
            <div className="log-container">
                {logs.map((log, i) => (
                    <div key={i} className="log-entry">{log}</div>
                ))}
                <div ref={logEndRef} />
            </div>
        </div>
    );
}



const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
