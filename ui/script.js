// Tab switching logic
        function switchTab(tabName) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));

            document.getElementById(`tab-${tabName}-btn`).classList.add('active');
            document.getElementById(`panel-${tabName}`).classList.add('active');

            // Initialize camera for visible tab
            if (tabName === 'pipeline') {
                initCamera('pipe-person-video', 'user', 'pipe-person-fallback');
                initCamera('pipe-doc-video', 'environment', 'pipe-doc-fallback');
            } else if (tabName === 'ocr') {
                initCamera('admin-ocr-video', 'environment', 'admin-ocr-fallback');
            } else if (tabName === 'face') {
                initCamera('admin-face1-video', 'user', 'admin-face1-fallback');
                initCamera('admin-face2-video', 'environment', 'admin-face2-fallback');
            }
        }

        // Helper: safe HTML escaping
        function escapeHtml(str) {
            if (str === null || str === undefined) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // Helper: normalize and deduplicate extracted fields to ensure each field appears once
        function getDeduplicatedFields(fieldsObj) {
            if (!fieldsObj || typeof fieldsObj !== 'object') return [];

            const CANONICAL_MAP = {
                'name': 'Full Name',
                'fullname': 'Full Name',
                'full_name': 'Full Name',
                'full name': 'Full Name',
                'given_name': 'Full Name',
                'given_names': 'Full Name',
                'surname': 'Full Name',
                'holder': 'Full Name',
                'document_number': 'Document Number',
                'document number': 'Document Number',
                'passport_number': 'Document Number',
                'passport number': 'Document Number',
                'passport_no': 'Document Number',
                'doc_no': 'Document Number',
                'id_number': 'Document Number',
                'aadhaar_number': 'Document Number',
                'aadhaar number': 'Document Number',
                'dob': 'Date of Birth',
                'date_of_birth': 'Date of Birth',
                'date of birth': 'Date of Birth',
                'birth_date': 'Date of Birth',
                'expiry': 'Date of Expiry',
                'date_of_expiry': 'Date of Expiry',
                'date of expiry': 'Date of Expiry',
                'expiration': 'Date of Expiry',
                'expiration_date': 'Date of Expiry',
                'valid_until': 'Date of Expiry',
                'valid_till': 'Date of Expiry',
                'nationality': 'Nationality',
                'citizenship': 'Nationality',
                'gender': 'Gender',
                'sex': 'Gender'
            };

            const preferredOrder = [
                'Full Name',
                'Document Number',
                'Date of Birth',
                'Date of Expiry',
                'Nationality',
                'Gender'
            ];

            const seen = new Map();
            for (const [rawKey, val] of Object.entries(fieldsObj)) {
                if (val === null || val === undefined || typeof val === 'object') continue;
                const strVal = String(val).trim();
                if (!strVal || strVal.toLowerCase() === 'none' || strVal.toLowerCase() === 'null') continue;

                const normKey = rawKey.toLowerCase().replace(/[\s_-]+/g, '');
                const cleanKey = rawKey.toLowerCase().replace(/[\s_-]+/g, ' ').trim();
                if (cleanKey === 'document type' || cleanKey === 'type') continue;

                const canonicalKey = CANONICAL_MAP[cleanKey] || CANONICAL_MAP[normKey] || rawKey;

                if (!seen.has(canonicalKey) || (!seen.get(canonicalKey) && strVal)) {
                    seen.set(canonicalKey, strVal);
                }
            }

            const entries = Array.from(seen.entries());
            entries.sort((a, b) => {
                const idxA = preferredOrder.indexOf(a[0]);
                const idxB = preferredOrder.indexOf(b[0]);
                if (idxA !== -1 && idxB !== -1) return idxA - idxB;
                if (idxA !== -1) return -1;
                if (idxB !== -1) return 1;
                return a[0].localeCompare(b[0]);
            });

            return entries;
        }

        // Helper: Render dedicated MRZ Extracted Fields card
        function renderMrzHtml(mrzData) {
            if (!mrzData || mrzData.error || !mrzData.document_number) {
                return `
                    <div style="background: rgba(11, 15, 25, 0.5); border: 1px dashed var(--border-color); border-radius: 10px; padding: 0.9rem 1.1rem; margin-top: 1rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-muted); font-size: 0.84rem;">
                            <span>ℹ️</span>
                            <span><strong>No MRZ Detected:</strong> Visual Inspection Zone (VIZ) extracted above. Machine-Readable Zone (MRZ) is standard on international passports and select travel IDs.</span>
                        </div>
                    </div>
                `;
            }

            const checks = mrzData.checks || {};
            const isValid = !!mrzData.is_valid;
            const badgeColor = isValid ? 'var(--success)' : 'var(--danger)';
            const badgeBg = isValid ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
            const mrzLines = mrzData.mrz_lines || [];

            // Format DOB: YYMMDD -> YYYY-MM-DD
            let fmtDob = mrzData.dob || '—';
            if (typeof fmtDob === 'string' && fmtDob.length === 6 && /^\d+$/.test(fmtDob)) {
                const yy = parseInt(fmtDob.substring(0, 2), 10);
                const century = yy > 30 ? '19' : '20';
                fmtDob = `${century}${fmtDob.substring(0, 2)}-${fmtDob.substring(2, 4)}-${fmtDob.substring(4, 6)}`;
            }

            // Format Expiry: YYMMDD -> 20YY-MM-DD
            let fmtExp = mrzData.expiry || '—';
            if (typeof fmtExp === 'string' && fmtExp.length === 6 && /^\d+$/.test(fmtExp)) {
                fmtExp = `20${fmtExp.substring(0, 2)}-${fmtExp.substring(2, 4)}-${fmtExp.substring(4, 6)}`;
            }

            const cdPill = (valid) => valid 
                ? `<span title="Check Digit verified per ICAO 9303 modulo-10 algorithm" style="font-size: 0.68rem; font-weight: 700; color: #34d399; background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 7px; border-radius: 4px;">✅ CHECK DIGIT VALID</span>`
                : `<span title="Check Digit calculation mismatch (possible OCR glare or altered number)" style="font-size: 0.68rem; font-weight: 700; color: #f87171; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 7px; border-radius: 4px;">❌ CHECK DIGIT FAILED</span>`;

            return `
                <div style="background: rgba(11, 15, 25, 0.75); border: 1px solid ${isValid ? 'rgba(56, 189, 248, 0.35)' : 'rgba(239, 68, 68, 0.4)'}; border-radius: 12px; padding: 1.25rem; margin-top: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.9rem; flex-wrap: wrap; gap: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 1.15rem;">🪪</span>
                            <div>
                                <h4 style="font-size: 0.98rem; font-weight: 800; color: #38bdf8; margin: 0;">Machine-Readable Zone (MRZ) Extracted Fields</h4>
                                <span style="font-size: 0.72rem; color: var(--text-muted);">ICAO Doc 9303 TD3 7-3-1 Modulo-10 Cryptographic Validation</span>
                            </div>
                        </div>
                        <span style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}; padding: 0.25rem 0.65rem; border-radius: 6px; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.04em;">
                            ${isValid ? '✅ CHECKSUMS PASSED' : '⚠️ CHECKSUM ANOMALY'}
                        </span>
                    </div>

                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.6rem; margin-bottom: 0.9rem;">
                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Document Number</div>
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.2rem;">
                                <span style="font-size: 0.95rem; font-weight: 800; color: #f8fafc; font-family: 'JetBrains Mono', monospace;">${escapeHtml(mrzData.document_number || '—')}</span>
                                ${checks.document_number_valid !== undefined ? cdPill(checks.document_number_valid) : ''}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Full Name (MRZ)</div>
                            <div style="font-size: 0.92rem; font-weight: 800; color: #f8fafc; margin-top: 0.2rem;">
                                ${escapeHtml(`${mrzData.given_names || ''} ${mrzData.surname || ''}`.trim() || '—')}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Date of Birth</div>
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.2rem;">
                                <span style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; font-family: 'JetBrains Mono', monospace;">${escapeHtml(fmtDob)}</span>
                                ${checks.dob_valid !== undefined ? cdPill(checks.dob_valid) : ''}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Date of Expiry</div>
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.2rem;">
                                <span style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; font-family: 'JetBrains Mono', monospace;">${escapeHtml(fmtExp)}</span>
                                ${checks.expiry_valid !== undefined ? cdPill(checks.expiry_valid) : ''}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Nationality / Country</div>
                            <div style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; margin-top: 0.2rem;">
                                ${escapeHtml(mrzData.nationality || mrzData.country || '—')}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Sex / Gender</div>
                            <div style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; margin-top: 0.2rem;">
                                ${escapeHtml(mrzData.gender || '—')}
                            </div>
                        </div>

                        <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Composite Check Digit</div>
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-top: 0.2rem;">
                                <span style="font-size: 0.82rem; color: var(--text-muted);">Overall Modulo-10:</span>
                                ${checks.composite_valid !== undefined ? cdPill(checks.composite_valid) : ''}
                            </div>
                        </div>
                    </div>

                    ${mrzLines.length > 0 ? `
                        <div style="margin-top: 0.75rem;">
                            <div style="font-size: 0.72rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.35rem;">Raw MRZ Lines (ICAO 9303 OCR-B)</div>
                            <pre style="background: #04070e; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 0.6rem 0.8rem; font-family: 'JetBrains Mono', monospace; font-size: 0.82rem; color: #38bdf8; letter-spacing: 0.12em; line-height: 1.5; overflow-x: auto;">${mrzLines.map(l => escapeHtml(l)).join('\n')}</pre>
                        </div>
                    ` : ''}
                </div>
            `;
        }

        // Helper: Render dedicated Aadhaar QR Code Decoded Data card
        function renderAadhaarQrHtml(qrData, crossChecks = []) {
            if (!qrData || qrData.status !== 'success') {
                return `
                    <div style="background: rgba(11, 15, 25, 0.5); border: 1px dashed var(--border-color); border-radius: 10px; padding: 0.9rem 1.1rem; margin-top: 1rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; color: var(--text-muted); font-size: 0.84rem;">
                            <span>ℹ️</span>
                            <span><strong>No Aadhaar QR Code Decoded:</strong> Upload the QR code image from the back of the physical card, PVC card, or e-Aadhaar to enable cryptographic digital signature verification and demographic cross-checking.</span>
                        </div>
                    </div>
                `;
            }

            const isSigned = !!qrData.is_signed;
            const badgeColor = isSigned ? 'var(--success)' : '#38bdf8';
            const badgeBg = isSigned ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)';
            const qrType = qrData.qr_type || 'Secure QR Code';

            let photoHtml = '';
            if (qrData.photo_base64) {
                photoHtml = `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 0.75rem;">
                        <img src="data:image/jpeg;base64,${qrData.photo_base64}" style="max-height: 130px; border-radius: 8px; border: 2px solid #10b981; box-shadow: 0 4px 14px rgba(16,185,129,0.25);" alt="Aadhaar QR Photo">
                        <span style="font-size: 0.7rem; color: #34d399; font-weight: 700; margin-top: 0.45rem;">📷 UIDAI Embedded Photo</span>
                        <span style="font-size: 0.65rem; color: var(--text-muted);">JPEG2000 Decompressed</span>
                    </div>
                `;
            }

            let addressParts = [];
            if (qrData.careof) addressParts.push(`C/O: ${escapeHtml(qrData.careof)}`);
            if (qrData.house) addressParts.push(escapeHtml(qrData.house));
            if (qrData.street) addressParts.push(escapeHtml(qrData.street));
            if (qrData.landmark) addressParts.push(escapeHtml(qrData.landmark));
            if (qrData.locality) addressParts.push(escapeHtml(qrData.locality));
            if (qrData.vtc) addressParts.push(escapeHtml(qrData.vtc));
            if (qrData.post_office) addressParts.push(`PO: ${escapeHtml(qrData.post_office)}`);
            if (qrData.district) addressParts.push(escapeHtml(qrData.district));
            if (qrData.state) addressParts.push(escapeHtml(qrData.state));
            if (qrData.pincode) addressParts.push(`PIN: ${escapeHtml(qrData.pincode)}`);
            const formattedAddress = addressParts.length > 0 ? addressParts.join(', ') : (qrData.address || '—');

            let crossCheckHtml = '';
            if (crossChecks && crossChecks.length > 0) {
                const aadhaarCross = crossChecks.filter(cc => /Aadhaar|Holder|Name|DOB|Gender|UID/i.test(cc.check || ''));
                if (aadhaarCross.length > 0) {
                    crossCheckHtml = `
                        <div style="margin-top: 1rem; padding: 0.85rem 1rem; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px;">
                            <div style="font-size: 0.84rem; font-weight: 800; color: #38bdf8; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.4rem;">
                                <span>🔍</span>
                                <span>Cryptographic Cross-Check: Visual Card OCR (VIZ) vs Secure QR Data</span>
                            </div>
                            <div style="display: flex; flex-direction: column; gap: 0.4rem;">
                                ${aadhaarCross.map(cc => {
                                    const match = !!cc.match;
                                    const mColor = match ? 'var(--success)' : 'var(--danger)';
                                    return `
                                        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.82rem; border-bottom: 1px dashed rgba(255,255,255,0.06); padding-bottom: 0.25rem;">
                                            <span><strong>${escapeHtml(cc.check)}:</strong> Card: <em>'${escapeHtml(cc.visual_value)}'</em> vs QR: <em>'${escapeHtml(cc.qr_value)}'</em></span>
                                            <span style="font-weight: 800; color: ${mColor}; font-size: 0.74rem; background: ${match ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; border: 1px solid ${mColor}; padding: 2px 7px; border-radius: 4px;">${match ? '✅ MATCH' : '❌ MISMATCH'}</span>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    `;
                }
            }

            return `
                <div style="background: rgba(11, 15, 25, 0.8); border: 1px solid ${isSigned ? 'rgba(16, 185, 129, 0.4)' : 'rgba(56, 189, 248, 0.4)'}; border-radius: 12px; padding: 1.25rem; margin-top: 1rem; box-shadow: 0 8px 24px rgba(0,0,0,0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.9rem; flex-wrap: wrap; gap: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span style="font-size: 1.25rem;">🪪</span>
                            <div>
                                <h4 style="font-size: 1rem; font-weight: 800; color: #34d399; margin: 0;">UIDAI Aadhaar QR Code Decoded Data</h4>
                                <span style="font-size: 0.72rem; color: var(--text-muted);">${escapeHtml(qrType)} • RSA 2048-bit Digital Envelope</span>
                            </div>
                        </div>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <span style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}; padding: 0.25rem 0.65rem; border-radius: 6px; font-weight: 800; font-size: 0.8rem; letter-spacing: 0.04em;">
                                ${isSigned ? '✅ UIDAI 2048-BIT SIGNED' : 'ℹ️ QR DECODED'}
                            </span>
                        </div>
                    </div>

                    <div style="display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-start;">
                        ${photoHtml}
                        
                        <div style="flex: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem;">
                            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Full Name (QR)</div>
                                <div style="font-size: 0.95rem; font-weight: 800; color: #f8fafc; margin-top: 0.2rem;">
                                    ${escapeHtml(qrData.name || '—')}
                                </div>
                            </div>

                            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Aadhaar UID</div>
                                <div style="font-size: 0.95rem; font-weight: 800; color: #38bdf8; font-family: 'JetBrains Mono', monospace; margin-top: 0.2rem;">
                                    ${qrData.last_4_digits ? `XXXX XXXX ${escapeHtml(qrData.last_4_digits)}` : (qrData.uid ? escapeHtml(qrData.uid) : '—')}
                                </div>
                            </div>

                            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Date of Birth</div>
                                <div style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; font-family: 'JetBrains Mono', monospace; margin-top: 0.2rem;">
                                    ${escapeHtml(qrData.dob || '—')}
                                </div>
                            </div>

                            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Gender</div>
                                <div style="font-size: 0.92rem; font-weight: 700; color: #cbd5e1; margin-top: 0.2rem;">
                                    ${escapeHtml(qrData.gender || '—')}
                                </div>
                            </div>

                            <div style="grid-column: 1 / -1; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: 0.6rem 0.75rem;">
                                <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700;">Full Registered Address</div>
                                <div style="font-size: 0.86rem; color: #e2e8f0; margin-top: 0.2rem; line-height: 1.45;">
                                    ${formattedAddress}
                                </div>
                            </div>
                        </div>
                    </div>

                    ${crossCheckHtml}
                </div>
            `;
        }

        // Camera Initialization with Safe Fallback for Mobile HTTP
        const activeStreams = {};
        const cameraFacingModes = {
            'pipe-person-video': 'user',
            'pipe-doc-video': 'environment',
            'admin-ocr-video': 'environment',
            'admin-face1-video': 'user',
            'admin-face2-video': 'environment'
        };

        async function initCamera(videoId, facingMode, fallbackId, force = false) {
            const video = document.getElementById(videoId);
            const fallback = document.getElementById(fallbackId);
            if (!video) return;
            if (activeStreams[videoId] && !force) return;

            if (activeStreams[videoId] && force) {
                try {
                    activeStreams[videoId].getTracks().forEach(t => t.stop());
                } catch (e) {
                    console.warn('Error stopping stream tracks:', e);
                }
                delete activeStreams[videoId];
            }

            cameraFacingModes[videoId] = facingMode;

            const parent = video.parentElement;
            const guide = parent ? parent.querySelector('.camera-guide') : null;

            // Check if mediaDevices is supported (strictly blocked on non-localhost HTTP on mobile)
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.warn(`Camera access not supported on this context (HTTP non-localhost) for ${videoId}`);
                if (fallback) {
                    fallback.style.display = 'flex';
                    fallback.innerHTML = `
                        <span style="font-size: 1.5rem; margin-bottom: 0.25rem;">🔒</span>
                        <strong style="color: #f8fafc; font-size: 0.9rem;">Live Camera Requires HTTPS</strong>
                        <small style="color: #94a3b8; font-size: 0.78rem; line-height: 1.35; max-width: 280px;">
                            Mobile browsers disable in-page camera streaming over plain HTTP. Start server with <code>--ssl</code> or tap below to snap & align in our interactive viewfinder:
                        </small>
                    `;
                }
                if (video) video.style.display = 'none';
                if (guide) guide.style.display = 'none';
                return;
            }

            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: { ideal: facingMode }, width: { ideal: 1280 }, height: { ideal: 720 } },
                    audio: false
                });
                video.srcObject = stream;
                activeStreams[videoId] = stream;
                if (fallback) fallback.style.display = 'none';
                video.style.display = 'block';
                if (guide) guide.style.display = 'flex';
            } catch (err) {
                console.warn(`getUserMedia failed with ideal ${facingMode} for ${videoId}:`, err.name, err.message);
                try {
                    const fallbackStream = await navigator.mediaDevices.getUserMedia({
                        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
                        audio: false
                    });
                    video.srcObject = fallbackStream;
                    activeStreams[videoId] = fallbackStream;
                    if (fallback) fallback.style.display = 'none';
                    video.style.display = 'block';
                    if (guide) guide.style.display = 'flex';
                } catch (err2) {
                    console.warn(`getUserMedia generic fallback failed for ${videoId}:`, err2.name, err2.message);
                    if (fallback) fallback.style.display = 'flex';
                    if (video) video.style.display = 'none';
                    if (guide) guide.style.display = 'none';
                }
            }
        }

        async function flipCamera(videoId, fallbackId) {
            const currentMode = cameraFacingModes[videoId] || 'user';
            const nextMode = (currentMode === 'user') ? 'environment' : 'user';
            console.log(`[CAMERA] Flipping ${videoId}: ${currentMode} -> ${nextMode}`);
            await initCamera(videoId, nextMode, fallbackId, true);
        }

        // ==============================================
        // INTERACTIVE CANVAS CROPPER CONTROLLER
        // ==============================================
        class ImageCropper {
            constructor() {
                this.modal = document.getElementById('cropper-modal');
                this.backdrop = document.getElementById('cropper-backdrop');
                this.stage = document.getElementById('cropper-stage');
                this.canvas = document.getElementById('cropper-canvas');
                this.ctx = this.canvas.getContext('2d');
                this.marquee = document.getElementById('cropper-marquee');
                this.faceOval = document.getElementById('cropper-face-oval');
                this.closeBtn = document.getElementById('cropper-close-btn');
                this.rotateBtn = document.getElementById('cropper-rotate-btn');
                this.applyBtn = document.getElementById('cropper-apply-btn');
                this.skipBtn = document.getElementById('cropper-skip-btn');
                this.presetBtns = document.querySelectorAll('.preset-btn');
                this.heading = document.getElementById('cropper-heading');

                this.currentImage = null;
                this.rotation = 0; // 0, 90, 180, 270
                this.cropBox = { x: 0, y: 0, w: 100, h: 100 };
                this.activeRatio = 'free';
                this.ratioValues = {
                    'free': null,
                    '1:1': 1.0,
                    'passport': 1.42,
                    'id_card': 1.586
                };

                this.stageBounds = { w: 0, h: 0 };
                this.dispBounds = { x: 0, y: 0, w: 0, h: 0, scale: 1 };
                this.isDragging = false;
                this.dragMode = null;
                this.dragStart = { x: 0, y: 0, boxX: 0, boxY: 0, boxW: 0, boxH: 0 };

                this.onApplyCallback = null;
                this.onSkipCallback = null;

                this._initEvents();
            }

            _initEvents() {
                this.closeBtn.addEventListener('click', () => this.close(true));
                this.backdrop.addEventListener('click', () => this.close(true));

                this.rotateBtn.addEventListener('click', () => {
                    this.rotation = (this.rotation + 90) % 360;
                    this.render();
                    this.resetCropBoxToCurrentRatio();
                });

                this.presetBtns.forEach(btn => {
                    btn.addEventListener('click', () => {
                        this.presetBtns.forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');
                        this.setRatio(btn.dataset.ratio);
                    });
                });

                this.applyBtn.addEventListener('click', () => this.applyCrop());
                this.skipBtn.addEventListener('click', () => this.skipCrop());

                const onStart = (clientX, clientY, target) => {
                    const handle = target.dataset.handle;
                    this.isDragging = true;
                    this.dragMode = handle || 'move';
                    this.dragStart = {
                        x: clientX,
                        y: clientY,
                        boxX: this.cropBox.x,
                        boxY: this.cropBox.y,
                        boxW: this.cropBox.w,
                        boxH: this.cropBox.h
                    };
                };

                const onMove = (clientX, clientY) => {
                    if (!this.isDragging) return;
                    const dx = clientX - this.dragStart.x;
                    const dy = clientY - this.dragStart.y;
                    this.updateDrag(dx, dy);
                };

                const onEnd = () => {
                    this.isDragging = false;
                    this.dragMode = null;
                };

                this.marquee.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    onStart(e.clientX, e.clientY, e.target);
                });

                window.addEventListener('mousemove', (e) => {
                    if (this.isDragging) {
                        e.preventDefault();
                        onMove(e.clientX, e.clientY);
                    }
                });

                window.addEventListener('mouseup', () => onEnd());

                this.marquee.addEventListener('touchstart', (e) => {
                    if (e.touches.length === 1) {
                        e.preventDefault();
                        onStart(e.touches[0].clientX, e.touches[0].clientY, e.target);
                    }
                }, { passive: false });

                window.addEventListener('touchmove', (e) => {
                    if (this.isDragging && e.touches.length === 1) {
                        e.preventDefault();
                        onMove(e.touches[0].clientX, e.touches[0].clientY);
                    }
                }, { passive: false });

                window.addEventListener('touchend', () => onEnd());
                window.addEventListener('touchcancel', () => onEnd());
            }

            open(blob, slotType = 'doc', defaultPreset = null, onApply, onSkip, onCancel = null) {
                this.onApplyCallback = onApply;
                this.onSkipCallback = onSkip;
                this.onCancelCallback = onCancel;
                this.rotation = 0;
                this.slotType = slotType;

                if (slotType === 'face') {
                    this.heading.textContent = '✂️ Align & Crop Face';
                    this.activeRatio = defaultPreset || '1:1';
                    this.faceOval.style.display = 'block';
                    this.marquee.classList.add('face-mode');
                } else {
                    this.heading.textContent = '✂️ Align & Crop Document';
                    this.activeRatio = defaultPreset || 'passport';
                    this.faceOval.style.display = 'none';
                    this.marquee.classList.remove('face-mode');
                }

                this.presetBtns.forEach(btn => {
                    btn.classList.toggle('active', btn.dataset.ratio === this.activeRatio);
                });

                const url = URL.createObjectURL(blob);
                const img = new Image();
                img.onload = () => {
                    this.currentImage = img;
                    this.modal.style.display = 'flex';
                    requestAnimationFrame(() => {
                        this.render();
                        this.resetCropBoxToCurrentRatio();
                    });
                    URL.revokeObjectURL(url);
                };
                img.src = url;
            }

            close(isCancel = false) {
                this.modal.style.display = 'none';
                this.currentImage = null;
                if (isCancel && this.onCancelCallback) {
                    this.onCancelCallback();
                }
            }

            setRatio(ratio) {
                this.activeRatio = ratio;
                if (ratio === '1:1' && this.slotType === 'face') {
                    this.faceOval.style.display = 'block';
                    this.marquee.classList.add('face-mode');
                } else {
                    this.faceOval.style.display = 'none';
                    this.marquee.classList.remove('face-mode');
                }
                this.resetCropBoxToCurrentRatio();
            }

            resetCropBoxToCurrentRatio() {
                const d = this.dispBounds;
                if (!d.w || !d.h) return;
                const targetRatio = this.ratioValues[this.activeRatio];

                let w, h;
                if (this.slotType === 'face') {
                    w = d.w * 0.65;
                    h = targetRatio ? w / targetRatio : d.h * 0.65;
                } else {
                    w = d.w * 0.85;
                    h = targetRatio ? w / targetRatio : d.h * 0.85;
                }

                if (h > d.h * 0.95) {
                    h = d.h * 0.95;
                    if (targetRatio) w = h * targetRatio;
                }
                if (w > d.w * 0.95) {
                    w = d.w * 0.95;
                    if (targetRatio) h = w / targetRatio;
                }

                const x = d.x + (d.w - w) / 2;
                const y = d.y + (d.h - h) / 2;

                this.cropBox = { x, y, w, h };
                this.updateMarqueeStyle();
            }

            render() {
                if (!this.currentImage) return;

                const stageRect = this.stage.getBoundingClientRect();
                this.stageBounds = { w: stageRect.width, h: stageRect.height };

                const isRotated = (this.rotation === 90 || this.rotation === 270);
                const origW = this.currentImage.naturalWidth;
                const origH = this.currentImage.naturalHeight;
                const effW = isRotated ? origH : origW;
                const effH = isRotated ? origW : origH;

                const pad = 24;
                const availW = Math.max(100, this.stageBounds.w - pad * 2);
                const availH = Math.max(100, this.stageBounds.h - pad * 2);

                const scale = Math.min(availW / effW, availH / effH);
                const dispW = Math.round(effW * scale);
                const dispH = Math.round(effH * scale);
                const dispX = Math.round((this.stageBounds.w - dispW) / 2);
                const dispY = Math.round((this.stageBounds.h - dispH) / 2);

                this.dispBounds = { x: dispX, y: dispY, w: dispW, h: dispH, scale, effW, effH, origW, origH };

                this.canvas.width = dispW;
                this.canvas.height = dispH;
                this.canvas.style.left = `${dispX}px`;
                this.canvas.style.top = `${dispY}px`;
                this.canvas.style.width = `${dispW}px`;
                this.canvas.style.height = `${dispH}px`;

                this.ctx.clearRect(0, 0, dispW, dispH);
                this.ctx.save();
                this.ctx.translate(dispW / 2, dispH / 2);
                this.ctx.rotate((this.rotation * Math.PI) / 180);

                const drawW = (isRotated ? dispH : dispW);
                const drawH = (isRotated ? dispW : dispH);
                this.ctx.drawImage(this.currentImage, -drawW / 2, -drawH / 2, drawW, drawH);
                this.ctx.restore();
            }

            updateDrag(dx, dy) {
                const d = this.dispBounds;
                const s = this.dragStart;
                const ratio = this.ratioValues[this.activeRatio];
                const minSize = 40;

                if (this.dragMode === 'move') {
                    let newX = s.boxX + dx;
                    let newY = s.boxY + dy;
                    newX = Math.max(d.x, Math.min(d.x + d.w - s.boxW, newX));
                    newY = Math.max(d.y, Math.min(d.y + d.h - s.boxH, newY));
                    this.cropBox.x = newX;
                    this.cropBox.y = newY;
                } else {
                    let x1 = s.boxX;
                    let y1 = s.boxY;
                    let x2 = s.boxX + s.boxW;
                    let y2 = s.boxY + s.boxH;

                    const mode = this.dragMode;
                    if (mode.includes('w')) x1 = Math.min(x2 - minSize, Math.max(d.x, s.boxX + dx));
                    if (mode.includes('e')) x2 = Math.max(x1 + minSize, Math.min(d.x + d.w, s.boxX + s.boxW + dx));
                    if (mode.includes('n')) y1 = Math.min(y2 - minSize, Math.max(d.y, s.boxY + dy));
                    if (mode.includes('s')) y2 = Math.max(y1 + minSize, Math.min(d.y + d.h, s.boxY + s.boxH + dy));

                    let curW = x2 - x1;
                    let curH = y2 - y1;

                    if (ratio) {
                        if (mode === 'n' || mode === 's') {
                            curW = curH * ratio;
                            x1 = (s.boxX + s.boxW / 2) - curW / 2;
                            x2 = x1 + curW;
                        } else {
                            curH = curW / ratio;
                            if (mode.includes('n')) y1 = y2 - curH;
                            else y2 = y1 + curH;
                        }
                    }

                    if (x1 < d.x) { x1 = d.x; if (ratio) curH = (x2 - x1) / ratio; }
                    if (x2 > d.x + d.w) { x2 = d.x + d.w; if (ratio) curH = (x2 - x1) / ratio; }
                    if (y1 < d.y) { y1 = d.y; if (ratio) { curW = (y2 - y1) * ratio; x2 = x1 + curW; } }
                    if (y2 > d.y + d.h) { y2 = d.y + d.h; if (ratio) { curW = (y2 - y1) * ratio; x2 = x1 + curW; } }

                    this.cropBox = {
                        x: x1,
                        y: y1,
                        w: Math.max(minSize, x2 - x1),
                        h: Math.max(minSize, y2 - y1)
                    };
                }

                this.updateMarqueeStyle();
            }

            updateMarqueeStyle() {
                this.marquee.style.left = `${this.cropBox.x}px`;
                this.marquee.style.top = `${this.cropBox.y}px`;
                this.marquee.style.width = `${this.cropBox.w}px`;
                this.marquee.style.height = `${this.cropBox.h}px`;
            }

            applyCrop() {
                if (!this.currentImage || !this.onApplyCallback) return;

                const d = this.dispBounds;
                const normX = (this.cropBox.x - d.x) / d.w;
                const normY = (this.cropBox.y - d.y) / d.h;
                const normW = this.cropBox.w / d.w;
                const normH = this.cropBox.h / d.h;

                const offscreen = document.createElement('canvas');
                offscreen.width = d.effW;
                offscreen.height = d.effH;
                const oCtx = offscreen.getContext('2d');

                const isRotated = (this.rotation === 90 || this.rotation === 270);
                oCtx.translate(d.effW / 2, d.effH / 2);
                oCtx.rotate((this.rotation * Math.PI) / 180);
                const drawW = isRotated ? d.effH : d.effW;
                const drawH = isRotated ? d.effW : d.effH;
                oCtx.drawImage(this.currentImage, -drawW / 2, -drawH / 2, drawW, drawH);

                const srcX = Math.round(normX * d.effW);
                const srcY = Math.round(normY * d.effH);
                const srcW = Math.round(normW * d.effW);
                const srcH = Math.round(normH * d.effH);

                const cropCanvas = document.createElement('canvas');
                cropCanvas.width = Math.max(1, srcW);
                cropCanvas.height = Math.max(1, srcH);
                const cCtx = cropCanvas.getContext('2d');
                cCtx.drawImage(offscreen, srcX, srcY, srcW, srcH, 0, 0, cropCanvas.width, cropCanvas.height);

                cropCanvas.toBlob((blob) => {
                    this.onApplyCallback(blob);
                    this.close();
                }, 'image/jpeg', 0.95);
            }

            skipCrop() {
                if (!this.currentImage || !this.onSkipCallback) return;
                const d = this.dispBounds;
                const offscreen = document.createElement('canvas');
                offscreen.width = d.effW;
                offscreen.height = d.effH;
                const oCtx = offscreen.getContext('2d');

                const isRotated = (this.rotation === 90 || this.rotation === 270);
                oCtx.translate(d.effW / 2, d.effH / 2);
                oCtx.rotate((this.rotation * Math.PI) / 180);
                const drawW = isRotated ? d.effH : d.effW;
                const drawH = isRotated ? d.effW : d.effH;
                oCtx.drawImage(this.currentImage, -drawW / 2, -drawH / 2, drawW, drawH);

                offscreen.toBlob((blob) => {
                    this.onSkipCallback(blob);
                    this.close();
                }, 'image/jpeg', 0.95);
            }
        }

        window.alephCropper = new ImageCropper();

        // Setup image slot handler (supports camera snap, file upload, drag-and-drop, interactive crop)
        function bindImageSlot(prefix, isBackCam = false, slotType = 'doc') {
            const frame = document.getElementById(`${prefix}-frame`);
            const video = document.getElementById(`${prefix}-video`);
            const preview = document.getElementById(`${prefix}-preview`);
            const snapBtn = document.getElementById(`${prefix}-snap`);
            const retakeBtn = document.getElementById(`${prefix}-retake`);
            const cropBtn = document.getElementById(`${prefix}-crop`);
            const subGroup = document.getElementById(`${prefix}-subgroup`);
            const fileInput = document.getElementById(`${prefix}-file`);
            
            let rawBlob = null;
            let croppedBlob = null;

            function getActiveDocPreset() {
                if (slotType === 'face') return '1:1';
                let docVal = 'passport';
                if (prefix.startsWith('pipe-doc')) {
                    const el = document.getElementById('pipe-doc-type');
                    if (el) docVal = el.value;
                } else if (prefix.startsWith('admin-ocr')) {
                    const el = document.getElementById('admin-ocr-type');
                    if (el) docVal = el.value;
                }
                return (docVal === 'id_card' || docVal === 'driving_license') ? 'id_card' : 'passport';
            }

            function launchCropper(blob) {
                rawBlob = blob;
                const preset = getActiveDocPreset();
                window.alephCropper.open(
                    blob, 
                    slotType, 
                    preset,
                    (newCropped) => {
                        setSlotImage(newCropped);
                    },
                    (fullBlob) => {
                        setSlotImage(fullBlob);
                    },
                    () => {
                        // Fallback on modal close without cropping: default to full uncropped image
                        if (!croppedBlob) {
                            setSlotImage(blob);
                        }
                    }
                );
            }

            // Snap from video stream
            if (snapBtn && video) {
                snapBtn.addEventListener('click', () => {
                    if (!video.srcObject) {
                        fileInput.click();
                        return;
                    }
                    const canvas = document.createElement('canvas');
                    canvas.width = video.videoWidth || 1280;
                    canvas.height = video.videoHeight || 720;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                    canvas.toBlob((blob) => {
                        launchCropper(blob);
                    }, 'image/jpeg', 0.95);
                });
            }

            // File upload / native camera handler (supports images and PDFs)
            if (fileInput) {
                fileInput.addEventListener('change', async (e) => {
                    const file = e.target.files[0];
                    if (!file) return;

                    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
                    if (isPdf) {
                        try {
                            const quantifier = (slotType === 'face') ? 'person' : 'document';
                            const formData = new FormData();
                            formData.append(quantifier, file, file.name);

                            console.log(`[UPLOAD] Converting uploaded PDF (${file.name}) via /upload...`);
                            const uploadRes = await fetch('/upload', { method: 'POST', body: formData });
                            const uploadData = await uploadRes.json();

                            if (uploadData.status === 'success' && uploadData.uploads && uploadData.uploads[quantifier]) {
                                const imgUrl = uploadData.uploads[quantifier].url;
                                console.log(`[UPLOAD] PDF rendered to image at ${imgUrl}. Loading into cropper...`);
                                const imgRes = await fetch(imgUrl);
                                const imgBlob = await imgRes.blob();
                                launchCropper(imgBlob);
                            } else {
                                alert(`Failed to convert PDF: ${uploadData.error || 'Unknown error'}`);
                            }
                        } catch (err) {
                            console.error('PDF upload/render error:', err);
                            alert(`Error processing PDF document: ${err.message}`);
                        }
                    } else {
                        launchCropper(file);
                    }
                });
            }

            // Retake button
            if (retakeBtn) {
                retakeBtn.addEventListener('click', () => {
                    rawBlob = null;
                    croppedBlob = null;
                    preview.style.display = 'none';
                    preview.src = '';
                    if (frame) frame.classList.remove('has-preview');
                    if (video && activeStreams[video.id]) {
                        video.style.display = 'block';
                    }
                    if (snapBtn) snapBtn.style.display = 'block';
                    if (subGroup) subGroup.style.display = 'none';
                });
            }

            // Crop / Adjust button
            if (cropBtn) {
                cropBtn.addEventListener('click', () => {
                    if (rawBlob) {
                        launchCropper(rawBlob);
                    }
                });
            }

            function setSlotImage(blob) {
                croppedBlob = blob;
                const url = URL.createObjectURL(blob);
                preview.src = url;
                preview.style.display = 'block';
                if (frame) frame.classList.add('has-preview');
                if (video) video.style.display = 'none';
                if (snapBtn) snapBtn.style.display = 'none';
                if (subGroup) subGroup.style.display = 'flex';
            }

            return {
                getBlob: () => croppedBlob || rawBlob,
                setBlob: setSlotImage
            };
        }

        // Dynamic Document Guide Updates based on document selection
        function updateDocGuides(docType) {
            const isAadhaar = (docType === 'aadhaar');
            const isCard = (docType === 'id_card' || docType === 'aadhaar' || docType === 'driving_license');

            const pipeAadhaarCard = document.getElementById('pipe-aadhaar-qr-card');
            if (pipeAadhaarCard) {
                pipeAadhaarCard.style.display = isAadhaar ? 'block' : 'none';
            }
            const adminAadhaarCard = document.getElementById('admin-aadhaar-qr-card');
            if (adminAadhaarCard) {
                adminAadhaarCard.style.display = isAadhaar ? 'block' : 'none';
            }

            const cutouts = ['pipe-doc-cutout', 'admin-ocr-cutout', 'admin-face2-cutout'];
            const boxes = ['pipe-doc-box', 'admin-ocr-box', 'admin-face2-box'];
            const brackets = ['pipe-doc-brackets', 'admin-ocr-brackets', 'admin-face2-brackets'];
            const captions = ['pipe-doc-caption', 'admin-ocr-caption', 'admin-face2-caption'];

            cutouts.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.setAttribute('y', isCard ? '46' : '38');
                    el.setAttribute('height', isCard ? '208' : '224');
                    el.setAttribute('rx', isCard ? '16' : '10');
                }
            });

            boxes.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    el.setAttribute('y', isCard ? '46' : '38');
                    el.setAttribute('height', isCard ? '208' : '224');
                    el.setAttribute('rx', isCard ? '16' : '10');
                    el.classList.toggle('id_card', isCard);
                }
            });

            brackets.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    const y1 = isCard ? 46 : 38;
                    const y2 = isCard ? 254 : 262;
                    el.setAttribute('d', `M 55,${y1} L 35,${y1} L 35,${y1+20} M 345,${y1} L 365,${y1} L 365,${y1+20} M 35,${y2-20} L 35,${y2} L 55,${y2} M 365,${y2-20} L 365,${y2} L 345,${y2}`);
                    el.classList.toggle('id_card', isCard);
                }
            });

            captions.forEach(id => {
                const el = document.getElementById(id);
                if (el) {
                    if (isAadhaar) {
                        el.textContent = 'Align Aadhaar Card Inside Frame';
                    } else if (isCard) {
                        el.textContent = 'Align ID Card Inside Frame';
                    } else {
                        el.textContent = 'Align Passport Inside Frame';
                    }
                }
            });
        }

        const pipeDocTypeSelect = document.getElementById('pipe-doc-type');
        if (pipeDocTypeSelect) {
            pipeDocTypeSelect.addEventListener('change', (e) => {
                updateDocGuides(e.target.value);
            });
        }
        const adminOcrTypeSelect = document.getElementById('admin-ocr-type');
        if (adminOcrTypeSelect) {
            adminOcrTypeSelect.addEventListener('change', (e) => {
                updateDocGuides(e.target.value);
            });
        }

        // Bind slots
        const pipePersonSlot = bindImageSlot('pipe-person', false, 'face');
        const pipeDocSlot = bindImageSlot('pipe-doc', true, 'doc');
        const adminOcrSlot = bindImageSlot('admin-ocr', true, 'doc');
        const adminFace1Slot = bindImageSlot('admin-face1', false, 'face');
        const adminFace2Slot = bindImageSlot('admin-face2', true, 'doc');

        // Flip Camera Event Listeners
        function bindCameraFlip(btnId, videoId, fallbackId) {
            const btn = document.getElementById(btnId);
            if (btn) {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    flipCamera(videoId, fallbackId);
                });
            }
        }
        bindCameraFlip('pipe-person-flip', 'pipe-person-video', 'pipe-person-fallback');
        bindCameraFlip('pipe-person-switch-float', 'pipe-person-video', 'pipe-person-fallback');
        bindCameraFlip('admin-face1-flip', 'admin-face1-video', 'admin-face1-fallback');
        bindCameraFlip('admin-face1-switch-float', 'admin-face1-video', 'admin-face1-fallback');

        // Aadhaar QR Handlers (Pipeline and Admin)
        let pipeAadhaarQrBlob = null;
        let adminAadhaarQrBlob = null;

        function setupAadhaarQrHandlers(prefix) {
            const fileInput = document.getElementById(`${prefix}-aadhaar-qr-file`);
            const filenameEl = document.getElementById(`${prefix}-aadhaar-qr-filename`);
            const previewBox = document.getElementById(`${prefix}-aadhaar-qr-preview-box`);
            const previewImg = document.getElementById(`${prefix}-aadhaar-qr-preview`);
            const decodeBtn = document.getElementById(`${prefix}-aadhaar-qr-decode-btn`);
            const statusEl = document.getElementById(`${prefix}-aadhaar-qr-instant-status`);

            if (!fileInput) return;

            fileInput.addEventListener('change', async (e) => {
                const file = e.target.files[0];
                if (!file) return;

                if (filenameEl) filenameEl.textContent = file.name;
                const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

                if (isPdf) {
                    try {
                        const formData = new FormData();
                        formData.append('aadhaar_qr', file, file.name);
                        if (statusEl) {
                            statusEl.textContent = 'Rendering PDF QR page...';
                            statusEl.style.color = '#38bdf8';
                        }
                        const res = await fetch('/upload', { method: 'POST', body: formData });
                        const data = await res.json();
                        if (data.status === 'success' && data.uploads && data.uploads.aadhaar_qr) {
                            const imgUrl = data.uploads.aadhaar_qr.url;
                            const imgRes = await fetch(imgUrl);
                            const blob = await imgRes.blob();
                            if (prefix === 'pipe') pipeAadhaarQrBlob = blob;
                            else adminAadhaarQrBlob = blob;
                            if (previewImg) previewImg.src = imgUrl;
                            if (previewBox) previewBox.style.display = 'flex';
                            if (decodeBtn) decodeBtn.style.display = 'inline-block';
                            if (statusEl) {
                                statusEl.textContent = 'PDF converted. Ready to decode.';
                                statusEl.style.color = 'var(--text-muted)';
                            }
                        } else {
                            if (statusEl) {
                                statusEl.textContent = `PDF Error: ${data.error || 'Failed'}`;
                                statusEl.style.color = 'var(--danger)';
                            }
                        }
                    } catch (err) {
                        if (statusEl) {
                            statusEl.textContent = `Error: ${err.message}`;
                            statusEl.style.color = 'var(--danger)';
                        }
                    }
                } else {
                    if (prefix === 'pipe') pipeAadhaarQrBlob = file;
                    else adminAadhaarQrBlob = file;
                    if (previewImg) previewImg.src = URL.createObjectURL(file);
                    if (previewBox) previewBox.style.display = 'flex';
                    if (decodeBtn) decodeBtn.style.display = 'inline-block';
                    if (statusEl) {
                        statusEl.textContent = 'QR loaded. Tap Decode to view payload.';
                        statusEl.style.color = 'var(--text-muted)';
                    }
                }
            });

            if (decodeBtn) {
                decodeBtn.addEventListener('click', async () => {
                    const blob = prefix === 'pipe' ? pipeAadhaarQrBlob : adminAadhaarQrBlob;
                    if (!blob) {
                        alert('Please select an Aadhaar QR code image first.');
                        return;
                    }

                    decodeBtn.disabled = true;
                    decodeBtn.textContent = '⏳ Decoding...';
                    if (statusEl) {
                        statusEl.textContent = 'Scanning 2048-bit RSA QR envelope...';
                        statusEl.style.color = '#38bdf8';
                    }

                    try {
                        const formData = new FormData();
                        formData.append('aadhaar_qr', blob, 'aadhaar_qr.jpg');
                        const res = await fetch('/decode_aadhaar_qr', { method: 'POST', body: formData });
                        const data = await res.json();

                        if (data.status === 'success' && data.aadhaar_qr) {
                            const qr = data.aadhaar_qr;
                            if (qr.status === 'success') {
                                if (statusEl) {
                                    statusEl.innerHTML = `<span style="color:var(--success); font-weight:700;">✅ Decoded: ${escapeHtml(qr.name || 'Cardholder')} (UID: ...${qr.last_4_digits || ''})</span>`;
                                }
                                const targetContainer = prefix === 'pipe' 
                                    ? document.getElementById('pipe-aadhaar-qr-container')
                                    : document.getElementById('admin-ocr-aadhaar-qr-container');
                                if (targetContainer) {
                                    targetContainer.innerHTML = renderAadhaarQrHtml(qr);
                                    targetContainer.style.display = 'block';
                                    targetContainer.scrollIntoView({ behavior: 'smooth' });
                                }
                            } else {
                                if (statusEl) {
                                    statusEl.innerHTML = `<span style="color:var(--danger); font-weight:700;">⚠️ ${escapeHtml(qr.error || 'Could not parse QR code')}</span>`;
                                }
                            }
                        } else {
                            if (statusEl) {
                                statusEl.innerHTML = `<span style="color:var(--danger); font-weight:700;">❌ ${escapeHtml(data.error || 'Failed to decode')}</span>`;
                            }
                        }
                    } catch (err) {
                        if (statusEl) {
                            statusEl.innerHTML = `<span style="color:var(--danger); font-weight:700;">❌ Network Error: ${escapeHtml(err.message)}</span>`;
                        }
                    } finally {
                        decodeBtn.disabled = false;
                        decodeBtn.textContent = '⚡ Decode QR Instantly';
                    }
                });
            }
        }
        setupAadhaarQrHandlers('pipe');
        setupAadhaarQrHandlers('admin');

        // Bind Slider Label updates
        function bindSlider(id, valId) {
            const slider = document.getElementById(id);
            const val = document.getElementById(valId);
            if (slider && val) {
                slider.addEventListener('input', (e) => {
                    val.textContent = e.target.value;
                });
            }
        }
        bindSlider('pipe-face-slider', 'pipe-face-val');
        bindSlider('pipe-ocr-slider', 'pipe-ocr-val');
        bindSlider('admin-ocr-strict-slider', 'admin-ocr-strict-val');
        bindSlider('admin-face-strict-slider', 'admin-face-strict-val');

        // Live Stopwatch / Execution Timer utility
        function startLiveTimer(timerElId, badgeElId) {
            const timerEl = document.getElementById(timerElId);
            const badgeEl = badgeElId ? document.getElementById(badgeElId) : null;
            const startTime = performance.now();

            if (timerEl) {
                timerEl.textContent = '⏱️ 0.0s';
                timerEl.style.display = 'inline-flex';
            }
            if (badgeEl) {
                badgeEl.style.display = 'none';
            }

            const interval = setInterval(() => {
                const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(1);
                if (timerEl) timerEl.textContent = `⏱️ ${elapsedSec}s`;
            }, 100);

            return {
                stop: (serverMs = null) => {
                    clearInterval(interval);
                    const elapsedSec = ((performance.now() - startTime) / 1000).toFixed(2);
                    if (timerEl) {
                        timerEl.style.display = 'none';
                    }
                    if (badgeEl) {
                        let text = `⏱️ ${elapsedSec}s`;
                        if (serverMs !== null && serverMs !== undefined && !isNaN(serverMs) && Number(serverMs) > 0) {
                            text += ` (${Math.round(serverMs)}ms engine)`;
                        }
                        badgeEl.textContent = text;
                        badgeEl.style.display = 'inline-flex';
                    }
                    return { elapsedSec: parseFloat(elapsedSec), elapsedMs: Math.round(performance.now() - startTime) };
                }
            };
        }

        // =======================================================
        // TAB 1: FULL PIPELINE EXECUTION
        // =======================================================
        document.getElementById('run-pipeline-btn').addEventListener('click', async () => {
            const personBlob = pipePersonSlot.getBlob();
            const docBlob = pipeDocSlot.getBlob();

            if (!personBlob || !docBlob) {
                alert('Please snap or upload both a Person photo and an ID Document photo.');
                return;
            }

            const btn = document.getElementById('run-pipeline-btn');
            const spinner = document.getElementById('pipeline-spinner');
            const resultsBox = document.getElementById('pipeline-results');

            btn.style.display = 'none';
            spinner.style.display = 'block';
            resultsBox.style.display = 'none';

            const timer = startLiveTimer('pipeline-live-timer', 'pipeline-time-badge');

            try {
                console.log('[PIPELINE] Uploading person and document images to /upload...');
                // 1. Upload files
                const formData = new FormData();
                formData.append('person', personBlob, 'person.jpg');
                formData.append('document', docBlob, 'document.jpg');
                if (pipeAadhaarQrBlob) {
                    formData.append('aadhaar_qr', pipeAadhaarQrBlob, 'aadhaar_qr.jpg');
                    console.log('[PIPELINE] Appended Aadhaar QR image to upload payload');
                }

                const uploadRes = await fetch('/upload', { method: 'POST', body: formData });
                if (!uploadRes.ok) throw new Error('Failed to upload image files to server');
                console.log('[PIPELINE] Upload completed successfully.');

                const faceStrict = document.getElementById('pipe-face-slider').value;
                const ocrStrict = document.getElementById('pipe-ocr-slider').value;
                const docType = document.getElementById('pipe-doc-type').value;

                console.log(`[PIPELINE] Executing Face Match & OCR in parallel: face_strict=${faceStrict}, ocr_strict=${ocrStrict}, doc_type=${docType}`);
                // 2. Parallel Face Match + OCR
                const [faceRes, ocrRes] = await Promise.all([
                    fetch(`/verify_photo?face_strictness=${faceStrict}`, { method: 'POST' }),
                    fetch(`/extract_text?type=${docType}&ocr_strictness=${ocrStrict}`, { method: 'POST' })
                ]);

                const faceData = await faceRes.json();
                const ocrData = await ocrRes.json();
                console.log('[PIPELINE] Face Verification response:', faceData);
                console.log('[PIPELINE] OCR & Document Validation response:', ocrData);

                // 3. Consolidate Scores across Modules via Risk Engine
                let consolidated = null;
                try {
                    console.log('[PIPELINE] Calling /consolidate_score...');
                    const consRes = await fetch('/consolidate_score', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ face_data: faceData, doc_data: ocrData })
                    });
                    if (consRes.ok) {
                        const consJson = await consRes.json();
                        if (consJson.status === 'success' && consJson.consolidated) {
                            consolidated = consJson.consolidated;
                            console.log('[PIPELINE] Risk Engine consolidated result:', consolidated);
                        }
                    }
                } catch (cErr) {
                    console.warn('[PIPELINE] Consolidate score API error (falling back to client scoring):', cErr);
                }

                // Compute timing
                const maxEngineMs = Math.max(
                    (faceData && faceData.verification && faceData.verification.processing_time_ms) || 0,
                    (ocrData && ocrData.processing_time_ms) || 0
                );
                const timing = timer.stop(maxEngineMs > 0 ? maxEngineMs : null);

                // Render Pipeline Results
                renderPipelineResults(faceData, ocrData, consolidated, timing);
                resultsBox.style.display = 'block';
                resultsBox.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                console.error('[PIPELINE] Pipeline Error:', err);
                timer.stop();
                alert(`Pipeline Error: ${err.message}`);
            } finally {
                btn.style.display = 'block';
                spinner.style.display = 'none';
            }
        });

        function renderPipelineResults(faceData, ocrData, consolidated, timing = null) {
            const overallBadge = document.getElementById('pipeline-overall-badge');
            const consContainer = document.getElementById('pipeline-consolidated-container');
            const faceContainer = document.getElementById('pipe-face-res');
            const ocrContainer = document.getElementById('pipe-ocr-res');

            const vFace = (faceData.status === 'success' && faceData.verification) ? faceData.verification : null;
            const faceScore = vFace ? (vFace.trust_score || 0) : 0;
            const isFaceMatch = vFace ? !!vFace.is_match : false;

            const vDoc = ocrData.validation || null;
            const docScore = vDoc ? (vDoc.score || 0) : 0;
            const isDocValid = vDoc ? !!vDoc.valid : false;
            const anomalies = vDoc ? (vDoc.anomalies || []) : [];
            const checks = vDoc ? (vDoc.checks || []) : [];

            // Compute client-side consolidated score fallback if server call is unavailable
            if (!consolidated) {
                const secChecks = checks.filter(c => /mrz|checksum|verhoeff|cross_check/i.test(c.field || ''));
                let secScore = docScore;
                if (secChecks.length > 0) {
                    const passed = secChecks.filter(c => c.status === 'CORRECT').length;
                    secScore = (passed / secChecks.length) * 100.0;
                }
                const stdScore = docScore;
                const wFace = 0.45, wSec = 0.35, wStd = 0.20;
                const rawScore = (faceScore * wFace) + (secScore * wSec) + (stdScore * wStd);

                const criticalFlags = [];
                let hasCrit = false;
                if (!isFaceMatch) {
                    criticalFlags.push('BIOMETRIC_MISMATCH: Live presenter does not match document photo');
                    hasCrit = true;
                }
                if (!isDocValid) {
                    criticalFlags.push(`DOCUMENT_INVALID: ${(vDoc && vDoc.decision && vDoc.decision.summary) || 'Failed format or security validation'}`);
                    hasCrit = true;
                }
                if (anomalies.some(a => String(a).includes('EXPIRED_DOCUMENT'))) {
                    criticalFlags.push('EXPIRED_TRAVEL_DOCUMENT: Document is expired and invalid for border crossing');
                    hasCrit = true;
                }
                if (anomalies.some(a => String(a).includes('CHECKSUM') || String(a).includes('TAMPERING'))) {
                    criticalFlags.push('SECURITY_INTEGRITY_COMPROMISED: Checksum or visual/MRZ mismatch detected');
                    hasCrit = true;
                }

                let finalScore = rawScore;
                if (hasCrit) finalScore = Math.min(finalScore, 48.0);
                finalScore = Math.round(Math.max(0, Math.min(100, finalScore)) * 10) / 10;

                consolidated = {
                    consolidated_score: finalScore,
                    score: finalScore,
                    raw_weighted_score: Math.round(rawScore * 10) / 10,
                    status: criticalFlags.length > 0 ? 'SUSPICIOUS_POINTS_FLAGGED' : 'NO_ANOMALIES',
                    suspicious_points: criticalFlags,
                    summary: criticalFlags.length > 0 ? `${criticalFlags.length} suspicious point(s) flagged for officer review.` : 'All checks verified without anomalies.',
                    is_cleared: criticalFlags.length === 0,
                    critical_flags: criticalFlags,
                    category_breakdown: [
                        {
                            category: "Biometric Face Match",
                            score: Math.round(faceScore * 10) / 10,
                            weight: 45.0,
                            contribution: Math.round(faceScore * 0.45 * 10) / 10,
                            passed: isFaceMatch,
                            status: isFaceMatch ? "PASS" : "FAIL",
                            rationale: "Physical person-to-document binding via 512D FaceNet embeddings. Ensures the presenter is the legitimate holder."
                        },
                        {
                            category: "Document Security & Checksums",
                            score: Math.round(secScore * 10) / 10,
                            weight: 35.0,
                            contribution: Math.round(secScore * 0.35 * 10) / 10,
                            passed: secScore >= 70.0 && !anomalies.some(a => String(a).includes('CHECKSUM')),
                            status: (secScore >= 70.0 && !anomalies.some(a => String(a).includes('CHECKSUM'))) ? "PASS" : "FAIL",
                            rationale: "ICAO 9303 / Verhoeff mathematical check-digit verification. High-confidence filter for altered numbers and tampered MRZs."
                        },
                        {
                            category: "Document Standards & Coherence",
                            score: Math.round(stdScore * 10) / 10,
                            weight: 20.0,
                            contribution: Math.round(stdScore * 0.20 * 10) / 10,
                            passed: isDocValid,
                            status: isDocValid ? "PASS" : "FAIL",
                            rationale: "Format compliance, current expiration status, legal age constraints, and cross-field temporal logic."
                        }
                    ],
                    individual_scores: {
                        face_verification: { score: Math.round(faceScore * 10) / 10, is_match: isFaceMatch },
                        doc_validation: { score: Math.round(docScore * 10) / 10, valid: isDocValid }
                    }
                };
            }

            // System Scoring & Highlighted Points
            const score = consolidated.consolidated_score !== undefined ? consolidated.consolidated_score : (consolidated.score || 0);
            const suspiciousPoints = consolidated.suspicious_points || consolidated.critical_flags || [];
            const hasSuspicious = suspiciousPoints.length > 0;
            const isHighConfidence = score >= 80 && !hasSuspicious;
            const isModerate = score >= 60 && !hasSuspicious;
            const scoreColor = isHighConfidence ? 'var(--success)' : (isModerate ? 'var(--warning)' : 'var(--danger)');
            const scoreGlow = isHighConfidence ? 'rgba(16, 185, 129, 0.22)' : (isModerate ? 'rgba(245, 158, 11, 0.22)' : 'rgba(239, 68, 68, 0.22)');
            const scoreBg = isHighConfidence ? 'rgba(16, 185, 129, 0.15)' : (isModerate ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)');

            // 1. Update Overall Header Status Badge (Displays only Score & suspicious points notice)
            overallBadge.className = isHighConfidence ? 'status-badge status-match' : (isModerate ? 'status-badge status-warning' : 'status-badge status-nomatch');
            overallBadge.textContent = hasSuspicious 
                ? `SCORE: ${score.toFixed(1)}/100 • ${suspiciousPoints.length} SUSPICIOUS POINT${suspiciousPoints.length > 1 ? 'S' : ''}` 
                : `SCORE: ${score.toFixed(1)}/100 • ALL CHECKS CLEAR`;

            // 2. Render Consolidated Score Dashboard
            const breakdown = consolidated.category_breakdown || [];
            let pillarsHtml = '';
            breakdown.forEach((pillar) => {
                const pPass = pillar.passed || pillar.status === 'PASS';
                const pColor = pPass ? 'var(--success)' : 'var(--danger)';
                const pIcon = pillar.category.includes('Face') ? '👤' : (pillar.category.includes('Security') ? '🔒' : '📋');
                pillarsHtml += `
                    <div class="pillar-card" style="border-left: 4px solid ${pColor};">
                        <div class="pillar-header">
                            <div style="display: flex; align-items: center; gap: 0.4rem;">
                                <span>${pIcon}</span>
                                <strong style="font-size: 0.88rem; color: var(--text-main);">${pillar.category}</strong>
                            </div>
                            <span class="pillar-weight-badge">${pillar.weight}% Weight</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: baseline;">
                            <span style="font-size: 1.4rem; font-weight: 800; color: ${pColor}; font-family: 'JetBrains Mono', monospace;">
                                ${pillar.score.toFixed(1)} <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: normal;">/ 100</span>
                            </span>
                            <span style="font-size: 0.82rem; font-weight: 700; color: #38bdf8;">
                                Contribution: +${pillar.contribution.toFixed(1)} pts
                            </span>
                        </div>
                        <div class="pillar-progress-track">
                            <div class="pillar-progress-fill" style="width: ${Math.min(100, Math.max(0, pillar.score))}%; background: ${pColor};"></div>
                        </div>
                        <div style="font-size: 0.76rem; color: var(--text-muted); line-height: 1.35; margin-top: 0.2rem;">
                            <strong>Why this weight:</strong> ${pillar.rationale}
                        </div>
                    </div>
                `;
            });

            // Highlighted Suspicious Points Section
            let suspiciousHtml = '';
            if (hasSuspicious) {
                suspiciousHtml = `
                    <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 10px; padding: 1.1rem 1.25rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; color: #f87171; font-weight: 800; font-size: 0.92rem; margin-bottom: 0.6rem;">
                            <span>🚩</span>
                            <span>Points Flagged as Suspicious by System (${suspiciousPoints.length}):</span>
                        </div>
                        <ul style="margin: 0; padding-left: 1.25rem; display: flex; flex-direction: column; gap: 0.45rem; font-size: 0.86rem; color: #fee2e2; line-height: 1.4;">
                            ${suspiciousPoints.map(pt => `<li><strong>${escapeHtml(pt)}</strong></li>`).join('')}
                        </ul>
                    </div>
                `;
            } else {
                suspiciousHtml = `
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 1.1rem 1.25rem;">
                        <div style="display: flex; align-items: center; gap: 0.5rem; color: #34d399; font-weight: 800; font-size: 0.92rem;">
                            <span>✅</span>
                            <span>No Suspicious Points Detected</span>
                        </div>
                        <div style="font-size: 0.84rem; color: #a7f3d0; margin-top: 0.35rem; line-height: 1.4;">
                            All facial biometrics, document formatting rules, and cryptographic/MRZ checksums verified consistently without anomalies.
                        </div>
                    </div>
                `;
            }

            consContainer.innerHTML = `
                <div class="consolidated-card" style="border-color: ${scoreColor}; box-shadow: 0 12px 36px ${scoreGlow};">
                    <div style="position: absolute; top: 0; left: 0; right: 0; height: 4px; background: ${scoreColor};"></div>
                    
                    <!-- Header -->
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem; margin-bottom: 1.5rem;">
                        <div>
                            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.3rem;">
                                <span style="font-size: 1.35rem;">🛡️</span>
                                <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-main); letter-spacing: -0.02em;">
                                    System Verification & Compliance Score
                                </h3>
                            </div>
                            <p style="font-size: 0.84rem; color: var(--text-muted);">
                                Multi-Pillar Scoring Engine • Objective Automated Signals for Officer Review
                            </p>
                        </div>

                        <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
                            <div style="display: flex; align-items: center; gap: 0.45rem; padding: 0.45rem 1rem; border-radius: 999px; background: ${scoreBg}; border: 1px solid ${scoreColor}; color: ${scoreColor}; font-weight: 800; font-size: 0.88rem; letter-spacing: 0.04em;">
                                <span>${hasSuspicious ? '⚠️' : '✅'}</span>
                                <span>SCORE: ${score.toFixed(1)} / 100</span>
                            </div>
                            <span style="padding: 0.45rem 0.8rem; border-radius: 6px; background: rgba(255,255,255,0.06); border: 1px solid var(--border-color); font-size: 0.8rem; font-weight: 700; color: var(--text-muted);">
                                FLAGS: <strong style="color: ${hasSuspicious ? 'var(--danger)' : 'var(--success)'};">${suspiciousPoints.length}</strong>
                            </span>
                            ${timing ? `
                            <span class="timer-pill" style="padding: 0.45rem 0.8rem; font-size: 0.8rem;">
                                ⏱️ ${timing.elapsedSec}s
                            </span>
                            ` : ''}
                        </div>
                    </div>

                    <!-- Hero Score & Suspicious Points Highlights -->
                    <div class="consolidated-hero">
                        <div class="consolidated-hero-score">
                            <div style="font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); font-weight: 700; margin-bottom: 0.25rem;">
                                Compliance Score
                            </div>
                            <div style="font-size: 3.2rem; font-weight: 900; line-height: 1; color: ${scoreColor}; font-family: 'JetBrains Mono', monospace;">
                                ${score.toFixed(1)}
                            </div>
                            <div style="font-size: 0.95rem; color: var(--text-muted); font-weight: 600; margin-top: 0.2rem;">
                                out of 100
                            </div>
                            <div style="margin-top: 0.75rem; width: 100%; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden;">
                                <div style="width: ${Math.min(100, Math.max(0, score))}%; height: 100%; background: ${scoreColor}; border-radius: 3px;"></div>
                            </div>
                            <div style="display: flex; justify-content: space-between; font-size: 0.68rem; color: var(--text-muted); margin-top: 0.4rem;">
                                <span>0 Min</span>
                                <span>50</span>
                                <span>100 Max</span>
                            </div>
                        </div>

                        <div style="display: flex; flex-direction: column; gap: 0.75rem; flex: 1;">
                            ${suspiciousHtml}
                        </div>
                    </div>

                    <!-- 3-Pillar Weighted Qualification Breakdown -->
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <h4 style="font-size: 0.88rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
                                ⚖️ Weighted Qualification Categories (Operational Importance vs AI Accuracy)
                            </h4>
                            <span style="font-size: 0.76rem; color: var(--text-muted);">
                                Normalized Weights Total: 100%
                            </span>
                        </div>
                        <div class="pillar-grid">
                            ${pillarsHtml}
                        </div>
                    </div>
                </div>
            `;

            // 3. Render Module 4 Individual Sub-Card (Face Match)
            if (vFace) {
                const isMatch = !!vFace.is_match;
                faceContainer.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-size: 1.1rem; font-weight: 800; color: ${isMatch ? 'var(--success)' : 'var(--danger)'};">
                            ${isMatch ? '✅ Face Match Consistent' : '⚠️ Biometric Discrepancy'}
                        </span>
                        <span style="font-size: 1.15rem; font-weight: 800; color: ${isMatch ? 'var(--success)' : 'var(--danger)'}; font-family: 'JetBrains Mono', monospace;">
                            Score: ${faceScore.toFixed(1)} / 100
                        </span>
                    </div>
                    <div style="font-size: 0.9rem; margin-bottom: 0.35rem;">
                        <strong>Individual Face Trust Score:</strong> ${faceScore.toFixed(1)}/100
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.35rem;">
                        Biometric Distance: <span style="color: #cbd5e1; font-family: 'JetBrains Mono', monospace;">${vFace.distance}</span> (Threshold Limit: ${vFace.threshold})
                    </div>
                    <div style="font-size: 0.8rem; color: #a78bfa;">
                        Model: ${vFace.model || 'Facenet512'} (${vFace.detector_backend || 'opencv'})
                    </div>
                `;
            } else {
                faceContainer.innerHTML = `<p style="color:var(--danger)">Error: ${faceData.error || (faceData.verification && faceData.verification.error) || 'Face verification failed'}</p>`;
            }

            // 4. Render Module 1 & 2 Individual Sub-Card (OCR & Validation)
            if (ocrData.status === 'warning') {
                ocrContainer.innerHTML = `
                    <div style="color: #fbbf24; font-size: 0.9rem; margin-bottom: 0.5rem;">⚠️ ${ocrData.message}</div>
                `;
            } else if (ocrData.status === 'success') {
                const f = ocrData.extracted_fields || {};
                const fieldEntries = getDeduplicatedFields(f);
                let fieldHtml = '';
                for (const [k, v] of fieldEntries) {
                    fieldHtml += `
                        <div style="font-size: 0.88rem; margin-bottom: 0.3rem; display: flex; justify-content: space-between; border-bottom: 1px dashed rgba(255,255,255,0.08); padding-bottom: 0.2rem;">
                            <span style="color: var(--text-muted); font-weight: 600;">${escapeHtml(k)}:</span>
                            <span style="color: ${v ? '#60a5fa' : '#64748b'}; font-weight: 600;">${escapeHtml(String(v)) || 'Not detected'}</span>
                        </div>
                    `;
                }

                let valHtml = '';
                if (ocrData.validation) {
                    const val = ocrData.validation;
                    const docPoints = val.suspicious_points || val.flags || [];
                    const hasDocSuspicious = docPoints.length > 0;
                    const vColor = hasDocSuspicious ? 'var(--danger)' : 'var(--success)';
                    
                    let suspiciousSubHtml = '';
                    if (hasDocSuspicious) {
                        suspiciousSubHtml = `
                            <div style="margin-top: 0.4rem; padding: 0.4rem 0.6rem; background: rgba(239, 68, 68, 0.12); border-radius: 6px; border: 1px solid rgba(239, 68, 68, 0.3);">
                                <div style="font-size: 0.76rem; font-weight: 700; color: #f87171; margin-bottom: 0.2rem;">Suspicious Points (${docPoints.length}):</div>
                                ${docPoints.map(p => `<div style="font-size: 0.74rem; color: #fca5a5;">• ${escapeHtml(p)}</div>`).join('')}
                            </div>
                        `;
                    }
                    valHtml = `
                        <div style="margin-top: 0.75rem; padding: 0.75rem 0.9rem; background: rgba(0,0,0,0.35); border-radius: 8px; border-left: 4px solid ${vColor};">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                                <strong style="font-size: 0.88rem; color: var(--text-main);">🛡️ Module 2 Document Validation:</strong>
                                <span style="font-size: 0.95rem; font-weight: 800; color: ${vColor}; font-family: 'JetBrains Mono', monospace;">
                                    Score: ${val.score}/100
                                </span>
                            </div>
                            <div style="color: var(--text-muted); font-size: 0.8rem; line-height: 1.4;">
                                ${escapeHtml(val.summary || (val.decision ? val.decision.summary : ''))}
                            </div>
                            ${suspiciousSubHtml}
                            ${(val.checks_summary) ? `
                                <div style="font-size: 0.78rem; color: #38bdf8; margin-top: 0.3rem; font-weight: 600;">
                                    Rules Checked: ${val.checks_summary.passed}/${val.checks_summary.total} verified
                                </div>
                            ` : ''}
                        </div>
                    `;
                }

                // Canvas drawing logic for bounding boxes
                let canvasWrapper = '';
                if (ocrData.raw_ocr && ocrData.raw_ocr.length > 0) {
                    canvasWrapper = `
                    <div style="position: relative; margin-top: 1rem; margin-bottom: 1rem; width: 100%; border: 1px solid var(--border-color); border-radius: var(--radius-sm); overflow: hidden;">
                        <img id="ocr-drawn-img" src="${document.getElementById('pipe-doc-preview').src}" style="display: block; width: 100%; height: auto;" />
                        <canvas id="ocr-drawn-canvas" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;"></canvas>
                    </div>
                    `;
                    setTimeout(() => {
                        const img = document.getElementById('ocr-drawn-img');
                        const canvas = document.getElementById('ocr-drawn-canvas');
                        if (img && canvas) {
                            canvas.width = img.clientWidth;
                            canvas.height = img.clientHeight;
                            const ctx = canvas.getContext('2d');
                            const scaleX = img.clientWidth / img.naturalWidth;
                            const scaleY = img.clientHeight / img.naturalHeight;
                            
                            ocrData.raw_ocr.forEach(word => {
                                const box = word.box;
                                const x = box[0][0] * scaleX;
                                const y = box[0][1] * scaleY;
                                const w = (box[1][0] - box[0][0]) * scaleX;
                                const h = (box[2][1] - box[0][1]) * scaleY;
                                
                                if (word.confidence < 0.6) {
                                    ctx.strokeStyle = '#ef4444'; // red
                                    ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
                                } else {
                                    ctx.strokeStyle = '#3b82f6'; // blue
                                    ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';
                                }
                                ctx.lineWidth = 2;
                                ctx.fillRect(x, y, w, h);
                                ctx.strokeRect(x, y, w, h);
                            });
                        }
                    }, 100);
                }

                ocrContainer.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
                        <span class="tag-pill" style="font-size: 0.75rem;">${f["Document Type"] || (ocrData.document_type ? ocrData.document_type.replace('_', ' ').toUpperCase() : 'Document')}</span>
                        <span style="font-size: 1.05rem; font-weight: 800; color: ${isDocValid ? 'var(--success)' : 'var(--danger)'}; font-family: 'JetBrains Mono', monospace;">
                            ${docScore.toFixed(1)} / 100
                        </span>
                    </div>
                    ${canvasWrapper}
                    <div style="margin-bottom: 0.85rem;">
                        <div style="font-size: 0.82rem; color: #60a5fa; font-weight: 700; margin-bottom: 0.45rem; text-transform: uppercase; letter-spacing: 0.05em;">
                            📋 Visual Zone (VIZ) Extracted Fields
                        </div>
                        ${fieldHtml}
                    </div>
                    ${renderMrzHtml(ocrData.mrz_parsed)}
                    ${valHtml}
                    ${(ocrData.raw_text || (ocrData.raw_ocr && ocrData.raw_ocr.length > 0)) ? `
                    <details style="margin-top: 0.75rem;">
                        <summary style="cursor: pointer; color: var(--text-muted); font-size: 0.8rem; font-weight: 600;">
                            📄 View Raw OCR Text (${(ocrData.raw_text || '').length} chars)
                        </summary>
                        <pre style="margin-top: 0.4rem; max-height: 140px; font-size: 0.78rem; white-space: pre-wrap; background: rgba(0,0,0,0.3); padding: 0.5rem; border-radius: 6px;">${escapeHtml(ocrData.raw_text || (ocrData.raw_ocr ? ocrData.raw_ocr.map(w => w.text).join(' ') : ''))}</pre>
                    </details>
                    ` : ''}
                `;

                // Render dedicated Aadhaar QR card in Pipeline tab if data available
                const pipeAadhaarContainer = document.getElementById('pipe-aadhaar-qr-container');
                const pipeDocType = document.getElementById('pipe-doc-type') ? document.getElementById('pipe-doc-type').value : '';
                const aadhaarQr = ocrData.aadhaar_qr_parsed || (ocrData.validation && ocrData.validation.aadhaar_qr);
                const crossChecks = (ocrData.validation && ocrData.validation.cross_checks) || [];
                if (pipeAadhaarContainer) {
                    if (aadhaarQr) {
                        pipeAadhaarContainer.innerHTML = renderAadhaarQrHtml(aadhaarQr, crossChecks);
                        pipeAadhaarContainer.style.display = 'block';
                    } else if (pipeDocType === 'aadhaar') {
                        pipeAadhaarContainer.innerHTML = renderAadhaarQrHtml(null);
                        pipeAadhaarContainer.style.display = 'block';
                    } else {
                        pipeAadhaarContainer.innerHTML = '';
                        pipeAadhaarContainer.style.display = 'none';
                    }
                }
            } else {
                ocrContainer.innerHTML = `<p style="color:var(--danger)">Error: ${ocrData.error || 'OCR failed'}</p>`;
            }
        }


        // =======================================================
        // TAB 2: OCR ADMIN TESTING ONLY
        // =======================================================
        document.getElementById('run-admin-ocr-btn').addEventListener('click', async () => {
            const docBlob = adminOcrSlot.getBlob();
            if (!docBlob) {
                alert('Please snap or upload a document photo to test OCR.');
                return;
            }

            const btn = document.getElementById('run-admin-ocr-btn');
            const spinner = document.getElementById('admin-ocr-spinner');
            const resultsBox = document.getElementById('admin-ocr-results');

            btn.style.display = 'none';
            spinner.style.display = 'block';
            resultsBox.style.display = 'none';

            const timer = startLiveTimer('admin-ocr-live-timer', 'admin-ocr-time-badge');

            try {
                console.log('[ADMIN-OCR] Starting OCR extraction test...');
                const formData = new FormData();
                formData.append('document', docBlob, 'document.jpg');
                console.log('[ADMIN-OCR] Uploading document to /upload...');
                const uploadRes = await fetch('/upload', { method: 'POST', body: formData });
                if (!uploadRes.ok) throw new Error('Upload failed');

                const strictness = document.getElementById('admin-ocr-strict-slider').value;
                const docType = document.getElementById('admin-ocr-type').value;

                console.log(`[ADMIN-OCR] Calling /extract_text?type=${docType}&ocr_strictness=${strictness}...`);
                const ocrRes = await fetch(`/extract_text?type=${docType}&ocr_strictness=${strictness}`, { method: 'POST' });
                const data = await ocrRes.json();
                console.log('[ADMIN-OCR] OCR Response received from backend:', data);

                const timing = timer.stop(data.processing_time_ms);
                renderAdminOcr(data, timing);
                resultsBox.style.display = 'block';
                resultsBox.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                console.error('[ADMIN-OCR] OCR Test Error:', err);
                timer.stop();
                alert(`OCR Test Error: ${err.message}`);
            } finally {
                btn.style.display = 'block';
                spinner.style.display = 'none';
            }
        });

        function renderAdminOcr(data, timing = null) {
            const badge = document.getElementById('admin-ocr-badge');
            const visualContainer = document.getElementById('admin-ocr-visual-container');
            const fieldsList = document.getElementById('admin-ocr-fields');
            const rawContainer = document.getElementById('admin-ocr-raw-container');
            const regionsTable = document.getElementById('admin-ocr-regions-table');
            const jsonPre = document.getElementById('admin-ocr-json');

            visualContainer.innerHTML = '';
            fieldsList.innerHTML = '';
            rawContainer.innerHTML = '';
            regionsTable.innerHTML = '';
            jsonPre.textContent = JSON.stringify(data, null, 2);

            if (data.status === 'warning') {
                badge.className = 'status-badge status-warning';
                badge.textContent = 'Low Text Detected';
                fieldsList.innerHTML = `
                    <li class="field-item" style="grid-column: 1 / -1; border-color: #f59e0b; background: rgba(245, 158, 11, 0.1);">
                        <span class="field-label" style="color: #fbbf24;">Notice</span>
                        <span class="field-value" style="color: white; font-size: 0.95rem;">${data.message}</span>
                    </li>
                `;
            } else if (data.status === 'error') {
                badge.className = 'status-badge status-nomatch';
                badge.textContent = 'Error';
                fieldsList.innerHTML = `<li class="field-item" style="grid-column: 1 / -1; color: var(--danger);">${data.error}</li>`;
                return;
            } else {
                badge.className = 'status-badge status-match';
                badge.textContent = `${data.document_type ? data.document_type.replace('_', ' ').toUpperCase() : 'EXTRACTED'}`;
            }

            // 1. Visual Text Regions Overlay
            const docPreview = document.getElementById('admin-ocr-preview');
            const imgSrc = docPreview && docPreview.src ? docPreview.src : null;
            const regions = data.regions_identified;

            if (imgSrc && regions && regions.image_dimensions) {
                const w = regions.image_dimensions.width || 800;
                const h = regions.image_dimensions.height || 600;
                const boxes = regions.text_boxes || [];
                const master = regions.master_crop || { x: 0, y: 0, w: w, h: h };

                let boxesSvg = '';
                boxes.forEach((b) => {
                    boxesSvg += `<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" fill="rgba(56, 189, 248, 0.12)" stroke="#38bdf8" stroke-width="1.8" rx="2" />`;
                });

                let masterSvg = '';
                if (master && master.w > 0 && master.h > 0) {
                    masterSvg = `
                        <rect x="${master.x}" y="${master.y}" width="${master.w}" height="${master.h}" fill="rgba(16, 185, 129, 0.08)" stroke="#10b981" stroke-width="2.5" stroke-dasharray="8 4" rx="4" />
                        <rect x="${master.x - 2}" y="${master.y - 2}" width="10" height="10" fill="#10b981" />
                        <rect x="${master.x + master.w - 8}" y="${master.y - 2}" width="10" height="10" fill="#10b981" />
                        <rect x="${master.x - 2}" y="${master.y + master.h - 8}" width="10" height="10" fill="#10b981" />
                        <rect x="${master.x + master.w - 8}" y="${master.y + master.h - 8}" width="10" height="10" fill="#10b981" />
                    `;
                }

                visualContainer.innerHTML = `
                    <div style="position: relative; max-width: 580px; margin: 0 auto 1.5rem auto; border-radius: 12px; overflow: hidden; border: 1px solid var(--border-color); background: #050811; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
                        <img src="${imgSrc}" style="width: 100%; display: block; filter: brightness(0.95);" alt="Analyzed Document Preview">
                        <svg style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
                            ${masterSvg}
                            ${boxesSvg}
                        </svg>
                        <div style="position: absolute; bottom: 8px; left: 8px; right: 8px; display: flex; justify-content: space-between; align-items: center; background: rgba(11, 15, 25, 0.88); padding: 6px 12px; border-radius: 8px; font-size: 0.78rem; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(8px);">
                            <span style="color: #38bdf8; font-weight: 700;">🔷 ${boxes.length} Text Blocks Detected</span>
                            <span style="color: #10b981; font-weight: 700;">🟩 Master Area: ${master.w}×${master.h}</span>
                        </div>
                    </div>
                `;
            }

            // 2. Extracted Fields Grid (deduplicated)
            const fields = data.extracted_fields || {};
            const fieldEntries = getDeduplicatedFields(fields);
            if (fieldEntries.length === 0) {
                fieldsList.innerHTML = `
                    <li class="field-item" style="grid-column: 1 / -1; color: var(--text-muted); padding: 1rem; text-align: center;">
                        <span>No structured fields could be automatically extracted from this view.</span>
                    </li>
                `;
            } else {
                for (const [key, val] of fieldEntries) {
                    const li = document.createElement('li');
                    li.className = 'field-item';
                    li.innerHTML = `
                        <span class="field-label">${escapeHtml(key)}</span>
                        <span class="field-value">${escapeHtml(String(val)) || '<span style="color:var(--text-muted); font-weight:normal;">Not detected</span>'}</span>
                    `;
                    fieldsList.appendChild(li);
                }
            }

            // 2.2 Dedicated MRZ Extracted Fields Section
            const mrzContainer = document.getElementById('admin-ocr-mrz-container');
            if (mrzContainer) {
                mrzContainer.innerHTML = renderMrzHtml(data.mrz_parsed);
            }

            // 2.3 Dedicated Aadhaar QR Section
            const aadhaarContainer = document.getElementById('admin-ocr-aadhaar-qr-container');
            const adminDocType = document.getElementById('admin-ocr-type') ? document.getElementById('admin-ocr-type').value : '';
            const adminAadhaarQr = data.aadhaar_qr_parsed || (data.validation && data.validation.aadhaar_qr);
            const adminCrossChecks = (data.validation && data.validation.cross_checks) || [];
            if (aadhaarContainer) {
                if (adminAadhaarQr) {
                    aadhaarContainer.innerHTML = renderAadhaarQrHtml(adminAadhaarQr, adminCrossChecks);
                } else if (adminDocType === 'aadhaar' || data.document_type === 'aadhaar') {
                    aadhaarContainer.innerHTML = renderAadhaarQrHtml(null);
                } else {
                    aadhaarContainer.innerHTML = '';
                }
            }

            // 2.5 Module 2 Document Validation Card
            const valContainer = document.getElementById('admin-ocr-validation-container');
            if (valContainer) valContainer.innerHTML = '';
            if (data.validation && valContainer) {
                const v = data.validation;
                const docPoints = v.suspicious_points || v.flags || [];
                const hasDocSuspicious = docPoints.length > 0;
                const statusColor = hasDocSuspicious ? 'var(--danger)' : 'var(--success)';
                const badgeBg = hasDocSuspicious ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)';

                let checksHtml = '';
                (v.checks || []).forEach(c => {
                    const ok = c.status === 'CORRECT';
                    const warn = c.status === 'WARNING';
                    const icon = ok ? '✅' : warn ? '⚠️' : '❌';
                    checksHtml += `
                        <div style="font-size: 0.84rem; padding: 0.4rem 0.6rem; background: rgba(0,0,0,0.25); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;">
                            <span style="display: flex; gap: 0.4rem; align-items: flex-start;">
                                <span>${icon}</span>
                                <span><strong>${escapeHtml(c.field)}</strong>: ${escapeHtml(c.reason)}</span>
                            </span>
                            <span style="font-size: 0.72rem; color: ${ok ? 'var(--success)' : warn ? 'var(--warning)' : 'var(--danger)'}; font-weight: 700; white-space: nowrap;">${c.status}</span>
                        </div>
                    `;
                });

                let flagsHtml = '';
                if (docPoints.length > 0) {
                    flagsHtml = `
                        <div style="margin-top: 0.75rem; padding: 0.75rem 1rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 8px;">
                            <div style="font-size: 0.82rem; font-weight: 700; color: #f87171; margin-bottom: 0.35rem;">🚩 Highlighted Suspicious Points (${docPoints.length}):</div>
                            ${docPoints.map(f => `<div style="font-size: 0.82rem; color: #fca5a5;">• ${escapeHtml(f)}</div>`).join('')}
                        </div>
                    `;
                } else {
                    flagsHtml = `
                        <div style="margin-top: 0.75rem; padding: 0.6rem 0.9rem; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; font-size: 0.82rem; color: #34d399;">
                            ✅ No suspicious points or integrity anomalies detected in document.
                        </div>
                    `;
                }

                let crossHtml = '';
                if (v.cross_checks && v.cross_checks.length > 0) {
                    crossHtml = `
                        <div style="margin-top: 0.75rem; padding: 0.75rem; background: rgba(56, 189, 248, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px;">
                            <div style="font-size: 0.82rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.35rem;">🔍 Visual vs MRZ Cross-Check:</div>
                            <div style="display: flex; flex-direction: column; gap: 0.3rem;">
                            ${v.cross_checks.map(cc => `
                                <div style="font-size: 0.82rem; display: flex; justify-content: space-between;">
                                    <span>${escapeHtml(cc.check)}: ${escapeHtml(cc.visual_value)} vs ${escapeHtml(cc.mrz_value)}</span>
                                    <span style="font-weight: 700; color: ${cc.match ? 'var(--success)' : 'var(--danger)'};">${cc.match ? 'MATCH' : 'MISMATCH'}</span>
                                </div>
                            `).join('')}
                            </div>
                        </div>
                    `;
                }

                valContainer.innerHTML = `
                    <div style="background: rgba(11, 15, 25, 0.7); border: 1px solid ${statusColor}; border-radius: 12px; padding: 1.25rem; margin-bottom: 1.25rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <span style="font-size: 1.1rem;">🛡️</span>
                                <h4 style="font-size: 1rem; color: var(--text-main); font-weight: 800;">Document Validation (Module 2)</h4>
                            </div>
                            <div style="display: flex; gap: 0.5rem; align-items: center;">
                                <span style="background: ${badgeBg}; color: ${statusColor}; border: 1px solid ${statusColor}; padding: 0.2rem 0.6rem; border-radius: 6px; font-weight: 800; font-size: 0.85rem; font-family: 'JetBrains Mono', monospace;">
                                    Score: ${v.score}/100
                                </span>
                            </div>
                        </div>
                        <p style="font-size: 0.88rem; color: var(--text-muted); margin-bottom: 0.75rem;">${escapeHtml(v.summary || (v.decision ? v.decision.summary : ''))}</p>
                        
                        <details open style="margin-top: 0.5rem;">
                            <summary style="cursor: pointer; color: #60a5fa; font-size: 0.85rem; font-weight: 700; margin-bottom: 0.5rem;">
                                Rule Verification Breakdown (${v.checks_summary ? v.checks_summary.passed : 0}/${v.checks_summary ? v.checks_summary.total : 0} passed)
                            </summary>
                            <div style="display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.4rem;">
                                ${checksHtml}
                            </div>
                        </details>
                        ${flagsHtml}
                        ${crossHtml}
                    </div>
                `;
            }

            // 3. Raw OCR Output & Multi-Pass breakdown
            const rawText = (data.raw_text !== undefined && data.raw_text !== null && data.raw_text !== '') 
                ? data.raw_text 
                : (data.raw_ocr && data.raw_ocr.length > 0 ? data.raw_ocr.map(w => w.text).join(' ') : '');
            const displayRaw = rawText.trim() || 'No raw text extracted';
            const charCount = displayRaw === 'No raw text extracted' ? 0 : displayRaw.length;
            const passes = data.ocr_passes || {
                psm11_sparse: (data.raw_ocr && data.raw_ocr.length > 0) ? data.raw_ocr.map(w => w.text).join('\n') : 'None',
                psm6_block: displayRaw
            };
            const engineMs = data.processing_time_ms ? `${data.processing_time_ms} ms engine` : null;
            const timeTag = timing ? `⏱️ ${timing.elapsedSec}s total${engineMs ? ` (${engineMs})` : ''}` : (engineMs ? `⏱️ ${engineMs}` : '');

            rawContainer.innerHTML = `
                <div style="background: rgba(11, 15, 25, 0.6); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.25rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.6rem;">
                            <h4 style="font-size: 0.95rem; color: #60a5fa; font-weight: 700;">📄 Raw OCR Output</h4>
                            ${timeTag ? `<span style="font-size: 0.75rem; color: #38bdf8; background: rgba(56, 189, 248, 0.12); border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 8px; border-radius: 999px; font-family: 'JetBrains Mono', monospace;">${timeTag}</span>` : ''}
                        </div>
                        <span style="font-size: 0.75rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">${charCount} characters</span>
                    </div>
                    <pre style="max-height: 200px; margin-bottom: 1rem; white-space: pre-wrap; font-size: 0.85rem; line-height: 1.5;">${escapeHtml(displayRaw)}</pre>
                    
                    <details>
                        <summary style="cursor: pointer; color: var(--text-muted); font-size: 0.85rem; font-weight: 600;">
                            📑 View Individual OCR Engine Passes (PSM 11 Sparse, PSM 6 Block, Specialized)
                        </summary>
                        <div style="margin-top: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem;">
                            <div>
                                <div style="font-size: 0.75rem; color: #a78bfa; font-weight: 700; margin-bottom: 0.25rem;">Pass A — Sparse Layout (PSM 11):</div>
                                <pre style="max-height: 120px; font-size: 0.8rem; white-space: pre-wrap;">${escapeHtml(passes.psm11_sparse || 'None')}</pre>
                            </div>
                            <div>
                                <div style="font-size: 0.75rem; color: #38bdf8; font-weight: 700; margin-bottom: 0.25rem;">Pass B — Adaptive Block Layout (PSM 6):</div>
                                <pre style="max-height: 120px; font-size: 0.8rem; white-space: pre-wrap;">${escapeHtml(passes.psm6_block || 'None')}</pre>
                            </div>
                            ${passes.specialized_pass ? `
                            <div>
                                <div style="font-size: 0.75rem; color: #10b981; font-weight: 700; margin-bottom: 0.25rem;">Pass C — Specialized Pass (MRZ / ID):</div>
                                <pre style="max-height: 120px; font-size: 0.8rem; white-space: pre-wrap;">${escapeHtml(passes.specialized_pass)}</pre>
                            </div>
                            ` : ''}
                        </div>
                    </details>
                </div>
            `;

            // 4. Identified Text Regions Table
            if (regions && regions.text_boxes && regions.text_boxes.length > 0) {
                let rows = '';
                regions.text_boxes.forEach((b, i) => {
                    rows += `
                        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                            <td style="padding: 6px 10px; color: #38bdf8;">#${i+1}</td>
                            <td style="padding: 6px 10px;">${b.x}</td>
                            <td style="padding: 6px 10px;">${b.y}</td>
                            <td style="padding: 6px 10px;">${b.w}</td>
                            <td style="padding: 6px 10px;">${b.h}</td>
                            <td style="padding: 6px 10px; color: var(--text-muted);">${b.w * b.h} px²</td>
                        </tr>
                    `;
                });

                regionsTable.innerHTML = `
                    <details>
                        <summary style="cursor: pointer; color: var(--text-muted); font-size: 0.85rem; font-weight: 600;">
                            📐 Identified Regions Coordinates Table (${regions.text_boxes.length} text blocks)
                        </summary>
                        <div style="margin-top: 0.5rem; max-height: 220px; overflow-y: auto; background: #080c14; border: 1px solid var(--border-color); border-radius: 8px;">
                            <table style="width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; text-align: left;">
                                <thead>
                                    <tr style="background: rgba(255,255,255,0.05); color: var(--text-muted); border-bottom: 1px solid var(--border-color);">
                                        <th style="padding: 6px 10px;">Box</th>
                                        <th style="padding: 6px 10px;">X</th>
                                        <th style="padding: 6px 10px;">Y</th>
                                        <th style="padding: 6px 10px;">Width</th>
                                        <th style="padding: 6px 10px;">Height</th>
                                        <th style="padding: 6px 10px;">Area</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${rows}
                                </tbody>
                            </table>
                        </div>
                    </details>
                `;
            }
        }


        // =======================================================
        // TAB 3: FACE MATCH ADMIN TESTING ONLY
        // =======================================================
        document.getElementById('run-admin-face-btn').addEventListener('click', async () => {
            const face1 = adminFace1Slot.getBlob();
            const face2 = adminFace2Slot.getBlob();

            if (!face1 || !face2) {
                alert('Please provide both Face 1 and Face 2 images to run Face Match verification.');
                return;
            }

            const btn = document.getElementById('run-admin-face-btn');
            const spinner = document.getElementById('admin-face-spinner');
            const resultsBox = document.getElementById('admin-face-results');

            btn.style.display = 'none';
            spinner.style.display = 'block';
            resultsBox.style.display = 'none';

            const timer = startLiveTimer('admin-face-live-timer', 'admin-face-time-badge');

            try {
                console.log('[ADMIN-FACE] Starting Face verification test...');
                const formData = new FormData();
                formData.append('person', face1, 'person.jpg');
                formData.append('document', face2, 'document.jpg');

                console.log('[ADMIN-FACE] Uploading face images to /upload...');
                const uploadRes = await fetch('/upload', { method: 'POST', body: formData });
                if (!uploadRes.ok) throw new Error('Upload failed');
                console.log('[ADMIN-FACE] Upload successful.');

                const strictness = document.getElementById('admin-face-strict-slider').value;
                const model = document.getElementById('admin-face-model').value;
                const detector = document.getElementById('admin-face-detector').value;

                console.log(`[ADMIN-FACE] Querying /verify_photo?face_strictness=${strictness}&model_name=${model}&detector_backend=${detector}...`);
                const verifyRes = await fetch(`/verify_photo?face_strictness=${strictness}&model_name=${model}&detector_backend=${detector}`, { method: 'POST' });
                const data = await verifyRes.json();
                console.log('[ADMIN-FACE] Face verification response:', data);

                const engineMs = (data.verification && data.verification.processing_time_ms) || null;
                const timing = timer.stop(engineMs);

                renderAdminFace(data, timing);
                resultsBox.style.display = 'block';
                resultsBox.scrollIntoView({ behavior: 'smooth' });

            } catch (err) {
                console.error('[ADMIN-FACE] Face Verification Error:', err);
                timer.stop();
                alert(`Face Verification Error: ${err.message}`);
            } finally {
                btn.style.display = 'block';
                spinner.style.display = 'none';
            }
        });

        function renderAdminFace(data, timing = null) {
            const badge = document.getElementById('admin-face-badge');
            const visualContainer = document.getElementById('admin-face-visual-container');
            const container = document.getElementById('admin-face-details');

            visualContainer.innerHTML = '';
            container.innerHTML = '';

            if (data.status === 'error' || (data.verification && data.verification.error)) {
                badge.className = 'status-badge status-nomatch';
                badge.textContent = 'Error';
                container.innerHTML = `<p style="color:var(--danger)">Error: ${data.error || (data.verification && data.verification.error) || 'Verification failed'}</p>`;
                return;
            }

            const v = data.verification;
            const isMatch = !!v.is_match;
            const faceTrust = v.trust_score !== undefined ? v.trust_score : (isMatch ? 90 : 35);
            badge.className = `status-badge ${isMatch ? 'status-match' : 'status-nomatch'}`;
            badge.textContent = `Score: ${faceTrust.toFixed(1)}/100`;

            // 1. Visual Face Bounding Boxes
            const pPreview = document.getElementById('admin-face1-preview');
            const dPreview = document.getElementById('admin-face2-preview');
            const pSrc = pPreview && pPreview.src ? pPreview.src : null;
            const dSrc = dPreview && dPreview.src ? dPreview.src : null;

            const pFaces = (v.detected_faces && v.detected_faces.person) || [];
            const dFaces = (v.detected_faces && v.detected_faces.document) || [];
            const pDims = (v.image_dimensions && v.image_dimensions.person) || { width: 400, height: 300 };
            const dDims = (v.image_dimensions && v.image_dimensions.document) || { width: 400, height: 300 };

            let pSvg = '';
            pFaces.forEach((f, i) => {
                const fa = f.facial_area || f;
                pSvg += `
                    <rect x="${fa.x}" y="${fa.y}" width="${fa.w}" height="${fa.h}" fill="rgba(16, 185, 129, 0.15)" stroke="#10b981" stroke-width="2.5" rx="4" />
                    <text x="${fa.x + 4}" y="${Math.max(16, fa.y - 6)}" fill="#10b981" font-size="14" font-weight="bold" font-family="sans-serif">Face #${i+1} (${Math.round((f.confidence||1)*100)}%)</text>
                `;
            });

            let dSvg = '';
            dFaces.forEach((f, i) => {
                const fa = f.facial_area || f;
                dSvg += `
                    <rect x="${fa.x}" y="${fa.y}" width="${fa.w}" height="${fa.h}" fill="rgba(56, 189, 248, 0.15)" stroke="#38bdf8" stroke-width="2.5" rx="4" />
                    <text x="${fa.x + 4}" y="${Math.max(16, fa.y - 6)}" fill="#38bdf8" font-size="14" font-weight="bold" font-family="sans-serif">Doc Face #${i+1} (${Math.round((f.confidence||1)*100)}%)</text>
                `;
            });

            visualContainer.innerHTML = `
                <div class="card-grid" style="margin-bottom: 1.5rem;">
                    <!-- Face 1 (Person) -->
                    <div style="background: rgba(11, 15, 25, 0.6); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h4 style="font-size: 0.85rem; color: #a78bfa; font-weight: 700;">👤 Face 1 Probe (${pFaces.length} detected)</h4>
                            <span style="font-size: 0.7rem; color: #10b981; font-weight: 700;">${pDims.width}×${pDims.height}</span>
                        </div>
                        <div style="position: relative; border-radius: 8px; overflow: hidden; background: #050811;">
                            ${pSrc ? `<img src="${pSrc}" style="width: 100%; display: block;" alt="Face 1 Probe">` : '<div style="height: 180px; display:flex; align-items:center; justify-content:center; color:var(--text-muted);">No image</div>'}
                            <svg style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;" viewBox="0 0 ${pDims.width} ${pDims.height}" preserveAspectRatio="none">
                                ${pSvg}
                            </svg>
                        </div>
                        <div style="margin-top: 0.5rem; font-size: 0.78rem; color: var(--text-muted);">
                            ${v.facial_areas && v.facial_areas.person ? `Dominant box: [x: ${v.facial_areas.person.x}, y: ${v.facial_areas.person.y}, w: ${v.facial_areas.person.w}, h: ${v.facial_areas.person.h}]` : 'No face coordinates'}
                        </div>
                    </div>

                    <!-- Face 2 (Document) -->
                    <div style="background: rgba(11, 15, 25, 0.6); padding: 1rem; border-radius: 12px; border: 1px solid var(--border-color);">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                            <h4 style="font-size: 0.85rem; color: #38bdf8; font-weight: 700;">📄 Face 2 Doc Photo (${dFaces.length} detected)</h4>
                            <span style="font-size: 0.7rem; color: #38bdf8; font-weight: 700;">${dDims.width}×${dDims.height}</span>
                        </div>
                        <div style="position: relative; border-radius: 8px; overflow: hidden; background: #050811;">
                            ${dSrc ? `<img src="${dSrc}" style="width: 100%; display: block;" alt="Face 2 Document">` : '<div style="height: 180px; display:flex; align-items:center; justify-content:center; color:var(--text-muted);">No image</div>'}
                            <svg style="position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;" viewBox="0 0 ${dDims.width} ${dDims.height}" preserveAspectRatio="none">
                                ${dSvg}
                            </svg>
                        </div>
                        <div style="margin-top: 0.5rem; font-size: 0.78rem; color: var(--text-muted);">
                            ${v.facial_areas && v.facial_areas.document ? `Dominant box: [x: ${v.facial_areas.document.x}, y: ${v.facial_areas.document.y}, w: ${v.facial_areas.document.w}, h: ${v.facial_areas.document.h}]` : 'No face coordinates'}
                        </div>
                    </div>
                </div>
            `;

            // Highlighted Suspicious Point for Face
            let faceSuspiciousHtml = '';
            if (!isMatch) {
                faceSuspiciousHtml = `
                    <div style="margin-bottom: 1.25rem; padding: 0.85rem 1.1rem; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 8px;">
                        <div style="font-size: 0.84rem; font-weight: 700; color: #f87171; margin-bottom: 0.25rem;">🚩 Highlighted Suspicious Point:</div>
                        <div style="font-size: 0.82rem; color: #fca5a5;">Biometric distance between presenter and document photo exceeds match threshold (Distance: ${v.distance}, limit: ${v.threshold}). Score: ${faceTrust.toFixed(1)}/100.</div>
                    </div>
                `;
            } else {
                faceSuspiciousHtml = `
                    <div style="margin-bottom: 1.25rem; padding: 0.75rem 1.1rem; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; font-size: 0.82rem; color: #34d399;">
                        ✅ Biometric facial distance is within threshold. No face anomalies detected.
                    </div>
                `;
            }

            // 2. Metrics & Details
            container.innerHTML = `
                ${faceSuspiciousHtml}
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
                    <div class="field-item">
                        <span class="field-label">Biometric Consistency</span>
                        <span class="field-value" style="color: ${isMatch ? 'var(--success)' : 'var(--danger)'};">
                            ${isMatch ? 'Match Consistent' : 'Discrepancy Flagged'}
                        </span>
                    </div>
                    <div class="field-item">
                        <span class="field-label">Biometric Score</span>
                        <span class="field-value">${faceTrust.toFixed(1)} / 100</span>
                    </div>
                    <div class="field-item">
                        <span class="field-label">Distance / Threshold</span>
                        <span class="field-value">${v.distance} (limit: ${v.threshold})</span>
                    </div>
                    <div class="field-item">
                        <span class="field-label">Model Engine</span>
                        <span class="field-value" style="color: #a78bfa;">${v.model || 'Facenet512'}</span>
                    </div>
                    <div class="field-item">
                        <span class="field-label">Processing Time</span>
                        <span class="field-value" style="color: #38bdf8; font-family: 'JetBrains Mono', monospace;">
                            ${v.processing_time_ms ? `${v.processing_time_ms} ms` : (timing ? `${timing.elapsedSec}s` : 'N/A')}
                        </span>
                    </div>
                </div>

                <!-- Detected Faces Raw Coordinates List -->
                <div style="background: rgba(11, 15, 25, 0.6); border: 1px solid var(--border-color); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem;">
                    <h4 style="font-size: 0.95rem; color: #a78bfa; margin-bottom: 0.75rem; font-weight: 700;">📐 Detected Face Bounding Boxes & Confidences</h4>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem;">
                        <div>
                            <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600;">Person Probe Faces:</div>
                            <pre style="max-height: 140px; font-size: 0.8rem;">${JSON.stringify(pFaces, null, 2)}</pre>
                        </div>
                        <div>
                            <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.35rem; font-weight: 600;">Document Photo Faces:</div>
                            <pre style="max-height: 140px; font-size: 0.8rem;">${JSON.stringify(dFaces, null, 2)}</pre>
                        </div>
                    </div>
                </div>

                <details>
                    <summary style="cursor:pointer; color:var(--text-muted); font-weight:600;">View Complete Raw Verification JSON</summary>
                    <pre style="margin-top:0.5rem;">${JSON.stringify(v, null, 2)}</pre>
                </details>
            `;
        }

        // Initialize on page load
        switchTab('pipeline');