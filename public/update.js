let currentReg = null;
let apiBaseUrl = window.location.origin + '/api';

if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    apiBaseUrl = 'http://localhost:5000/api';
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('findRegBtn').addEventListener('click', lookupRegistration);
    document.getElementById('payBalanceBtn').addEventListener('click', payBalance);
    document.getElementById('payDifferenceBtn').addEventListener('click', processUpdateAndPay);
});

async function lookupRegistration() {
    const email = document.getElementById('lookupEmail').value.trim();
    const nationalId = document.getElementById('lookupTtaId').value.trim();
    const errorEl = document.getElementById('lookupError');
    const btn = document.getElementById('findRegBtn');

    if (!email || !nationalId) {
        errorEl.textContent = "Please enter both your Email and TTA Member Number.";
        errorEl.style.display = "block";
        return;
    }

    btn.textContent = "Searching...";
    btn.disabled = true;
    errorEl.style.display = "none";

    try {
        const response = await fetch(`${apiBaseUrl}/registration/lookup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, nationalId: nationalId })
        });
        
        if (response.ok) {
            currentReg = await response.json();
            await showUpdateStep();
        } else {
            const data = await response.json();
            errorEl.textContent = data.error || "Registration not found.";
            errorEl.style.display = "block";
        }
    } catch (err) {
        errorEl.textContent = "Server error. Please try again later.";
        errorEl.style.display = "block";
        console.error(err);
    } finally {
        btn.textContent = "Find Registration";
        btn.disabled = false;
    }
}

async function showUpdateStep() {
    document.getElementById('lookupStep').style.display = "none";
    document.getElementById('updateStep').style.display = "block";
    
    document.getElementById('playerNameDisplay').textContent = `${currentReg.player.firstName} ${currentReg.player.lastName}`;

    const balance = currentReg.balanceDue || 0;
    if (balance > 0) {
        document.getElementById('balanceSection').style.display = "block";
        document.getElementById('balanceAmountDisplay').textContent = balance.toFixed(2);
    } else {
        document.getElementById('balanceSection').style.display = "none";
    }

    document.getElementById('oldPaidAmount').textContent = parseFloat(currentReg.finalTotal || 0).toFixed(2);
    
    renderUpdateEventsList();
    await applyEligibilityRestrictions();
    calculateUpdateTotals();
}

function renderUpdateEventsList() {
    document.querySelectorAll('#updateEventsContainer input[type="radio"][value=""]').forEach(r => r.checked = true);

    if (!currentReg.events) return;
    const regEventIds = currentReg.events.map(e => e.id);

    document.querySelectorAll('#updateEventsContainer input[type="radio"]:not([value=""])').forEach(radio => {
        const ev = JSON.parse(radio.value);
        if (regEventIds.includes(ev.id)) {
            radio.checked = true;
        }
    });
}

async function applyEligibilityRestrictions() {
    let playerRating = 0;
    const rcId = currentReg.player.rcId;
    
    if (rcId && rcId.toLowerCase() !== 'never played' && rcId.toLowerCase() !== 'n/a') {
        try {
            const res = await fetch(`${apiBaseUrl}/ratings-central/search?query=${rcId}`);
            if (res.ok) {
                const data = await res.json();
                if (data.players && data.players.length > 0) {
                    playerRating = parseInt(data.players[0].rating, 10);
                }
            }
        } catch (e) {
            console.warn("Could not fetch player rating for validation.");
        }
    }

    let ageIn2026 = 0;
    if (currentReg.player.dob) {
        const parts = currentReg.player.dob.split('/');
        if (parts.length === 3) {
            ageIn2026 = 2026 - parseInt(parts[2], 10);
        }
    }

    const gender = currentReg.player.gender || "";

    document.querySelectorAll('#updateEventsContainer input[type="radio"]:not([value=""])').forEach(radio => {
        const ev = JSON.parse(radio.value);
        const name = ev.name.toLowerCase();
        let disable = false;
        let reason = [];

        if (gender === 'Male' && (name.includes('women') || name.includes('girl'))) { disable = true; reason.push('Gender'); }
        if (gender === 'Female' && (name.includes('men') || name.includes('boy'))) { disable = true; reason.push('Gender'); }

        if (name.includes('under 11') && ageIn2026 >= 11) { disable = true; reason.push('Age'); }
        if (name.includes('under 13') && ageIn2026 >= 13) { disable = true; reason.push('Age'); }
        if (name.includes('under 15') && ageIn2026 >= 15) { disable = true; reason.push('Age'); }
        if (name.includes('under 17') && ageIn2026 >= 17) { disable = true; reason.push('Age'); }
        if (name.includes('under 19') && ageIn2026 >= 19) { disable = true; reason.push('Age'); }

        if (name.includes('over 30') && ageIn2026 < 30) { disable = true; reason.push('Age'); }
        if (name.includes('over 40') && ageIn2026 < 40) { disable = true; reason.push('Age'); }
        if (name.includes('over 50') && ageIn2026 < 50) { disable = true; reason.push('Age'); }
        if (name.includes('over 60') && ageIn2026 < 60) { disable = true; reason.push('Age'); }
        if (name.includes('over 70') && ageIn2026 < 70) { disable = true; reason.push('Age'); }
        if (name.includes('over 80') && ageIn2026 < 80) { disable = true; reason.push('Age'); }
        if (name.includes('veteran') && ageIn2026 < 30) { disable = true; reason.push('Age'); }

        if (playerRating > 0) {
            if (name.includes('under 1700') && playerRating >= 1700) { disable = true; reason.push('Rating'); }
            if (name.includes('under 1400') && playerRating >= 1400) { disable = true; reason.push('Rating'); }
            if (name.includes('under 1200') && playerRating >= 1200) { disable = true; reason.push('Rating'); }
            if (name.includes('under 1000') && playerRating >= 1000) { disable = true; reason.push('Rating'); }
            if (name.includes('under 800') && playerRating >= 800) { disable = true; reason.push('Rating'); }
        }

        if (disable) {
            radio.disabled = true;
            const label = radio.parentNode;
            label.style.color = '#94A3B8';
            label.style.textDecoration = 'line-through';
            
            const badge = document.createElement('span');
            badge.style.fontSize = '10px';
            badge.style.background = '#F1F5F9';
            badge.style.padding = '2px 6px';
            badge.style.borderRadius = '4px';
            badge.style.marginLeft = '8px';
            badge.style.textDecoration = 'none';
            badge.style.display = 'inline-block';
            badge.textContent = `Ineligible (${reason.join(', ')})`;
            
            label.appendChild(badge);
        }
    });
}

function calculateUpdateTotals() {
    const selectedEvents = [];
    let baseTotal = 0;
    
    document.querySelectorAll('#updateEventsContainer input[type="radio"]:not([value=""]):checked').forEach(rad => {
        const ev = JSON.parse(rad.value);
        selectedEvents.push(ev);
        baseTotal += parseFloat(ev.price);
    });

    const ttqLevy = 5.00;
    const discountAmount = parseFloat(currentReg.discountAmount || 0);
    let newFinalTotal = (baseTotal + ttqLevy) - discountAmount;
    if (newFinalTotal < 0) newFinalTotal = 0;
    
    document.getElementById('newTotalAmount').textContent = newFinalTotal.toFixed(2);
    
    const oldFinalTotal = parseFloat(currentReg.finalTotal || 0);
    const difference = Math.round((newFinalTotal - oldFinalTotal) * 100) / 100;
    
    document.getElementById('differenceAmount').textContent = difference.toFixed(2);
    
    const warningEl = document.getElementById('refundWarning');
    const payBtn = document.getElementById('payDifferenceBtn');
    
    if (difference < 0) {
        warningEl.style.display = "block";
        payBtn.disabled = false;
        payBtn.textContent = "SAVE CHANGES";
    } else if (difference === 0) {
        warningEl.style.display = "none";
        payBtn.disabled = false;
        payBtn.textContent = "SAVE CHANGES (FREE)";
    } else {
        warningEl.style.display = "none";
        payBtn.disabled = false;
        payBtn.textContent = "PROCEED TO SECURE PAYMENT";
    }

    const currentPartnerValues = {};
    document.querySelectorAll('#partnerInputsUpdate input').forEach(inp => {
        currentPartnerValues[inp.id] = inp.value;
    });

    const partnerSection = document.getElementById('doublesPartnerSectionUpdate');
    const partnerInputs = document.getElementById('partnerInputsUpdate');
    partnerInputs.innerHTML = '';
    let needsPartner = false;

    selectedEvents.forEach(ev => {
        if (ev.name.toLowerCase().includes('doubles')) {
            needsPartner = true;
            
            let savedPartner = currentPartnerValues[`partner_update_${ev.id}`];
            if (savedPartner === undefined) {
                savedPartner = (currentReg.doublesPartners && currentReg.doublesPartners[ev.name]) ? currentReg.doublesPartners[ev.name] : "";
            }
            
            partnerInputs.innerHTML += `
                <div class="form-group" style="margin-bottom: 10px;">
                    <label style="font-size: 13px;">Partner for ${ev.name}</label>
                    <input type="text" id="partner_update_${ev.id}" value="${savedPartner}" placeholder="Partner Name (or 'Partner Required')" required style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;" onchange="calculateUpdateTotals()">
                </div>
            `;
        }
    });

    partnerSection.style.display = needsPartner ? 'block' : 'none';
}

async function processUpdateAndPay() {
    const selectedEvents = [];
    document.querySelectorAll('#updateEventsContainer input[type="radio"]:not([value=""]):checked').forEach(chk => {
        selectedEvents.push(JSON.parse(chk.value));
    });

    const doublesPartners = {};
    selectedEvents.forEach(ev => {
        if (ev.name.toLowerCase().includes('doubles')) {
            const el = document.getElementById(`partner_update_${ev.id}`);
            if (el) doublesPartners[ev.name] = el.value;
        }
    });

    const oldFinalTotal = parseFloat(currentReg.finalTotal || 0);
    const newTotalText = parseFloat(document.getElementById('newTotalAmount').textContent);
    const difference = Math.round((newTotalText - oldFinalTotal) * 100) / 100;

    const btn = document.getElementById('payDifferenceBtn');
    
    if (difference <= 0) {
        btn.textContent = "Saving Changes...";
        btn.disabled = true;
        try {
            const response = await fetch(`${apiBaseUrl}/admin/registrations/${currentReg.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    events: selectedEvents,
                    doublesPartners: doublesPartners
                })
            });
            if (response.ok) {
                alert("Your registration has been updated successfully!");
                window.location.reload();
            } else {
                alert("Failed to update registration. Please try again.");
                btn.textContent = "SAVE CHANGES";
                btn.disabled = false;
            }
        } catch(err) {
            console.error(err);
            alert("Server error. Please try again.");
            btn.textContent = "SAVE CHANGES";
            btn.disabled = false;
        }
        return;
    }

    const payload = {
        reg_id: currentReg.id,
        events: selectedEvents,
        doublesPartners: doublesPartners
    };

    btn.textContent = "Processing...";
    btn.disabled = true;

    try {
        const response = await fetch(`${apiBaseUrl}/registration/update-checkout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            const data = await response.json();
            window.location.href = data.url;
        } else {
            const err = await response.json();
            alert("Error: " + (err.error || "Failed to process update"));
            btn.textContent = "PROCEED TO PAY DIFFERENCE";
            btn.disabled = false;
        }
    } catch(err) {
        console.error(err);
        alert("Server error. Please try again.");
        btn.textContent = "PROCEED TO PAY DIFFERENCE";
        btn.disabled = false;
    }
}

async function payBalance() {
    const btn = document.getElementById('payBalanceBtn');
    btn.textContent = "Processing...";
    btn.disabled = true;

    try {
        const response = await fetch(`${apiBaseUrl}/registration/pay-balance`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reg_id: currentReg.id })
        });

        if (response.ok) {
            const data = await response.json();
            window.location.href = data.url;
        } else {
            const err = await response.json();
            alert("Error: " + (err.error || "Failed to process balance payment"));
            btn.textContent = "Pay Balance Now";
            btn.disabled = false;
        }
    } catch(err) {
        console.error(err);
        alert("Server error. Please try again.");
        btn.textContent = "Pay Balance Now";
        btn.disabled = false;
    }
}