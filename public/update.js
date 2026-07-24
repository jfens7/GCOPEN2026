let currentReg = null;

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('findRegBtn').addEventListener('click', lookupRegistration);
    document.getElementById('payBalanceBtn').addEventListener('click', payBalance);
    document.getElementById('payDifferenceBtn').addEventListener('click', processUpdateAndPay);
});

async function lookupRegistration() {
    const nationalId = document.getElementById('lookupTtaId').value.trim();
    const dob = document.getElementById('lookupDob').value.trim();
    const errorEl = document.getElementById('lookupError');
    const btn = document.getElementById('findRegBtn');

    if (!nationalId || !dob) {
        errorEl.textContent = "Please enter both your TTA Member Number and DOB.";
        errorEl.style.display = "block";
        return;
    }

    btn.textContent = "Searching...";
    btn.disabled = true;
    errorEl.style.display = "none";

    try {
        const response = await fetch(`${API_BASE}/registration/lookup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nationalId: nationalId, dob: dob })
        });
        
        if (response.ok) {
            currentReg = await response.json();
            showUpdateStep();
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

function showUpdateStep() {
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
    calculateUpdateTotals();
}

function renderUpdateEventsList() {
    const eventsList = document.getElementById('updateEventsContainer');
    eventsList.innerHTML = "";
    
    const regEventIds = currentReg.events.map(e => e.id);
    
    masterEventsList.forEach(ev => {
        const isChecked = regEventIds.includes(ev.id) ? "checked" : "";
        eventsList.innerHTML += `
            <div style="margin-bottom: 5px;">
                <label style="cursor: pointer; font-weight: normal; font-size: 14px;">
                    <input type="checkbox" name="update_event" value='${JSON.stringify(ev)}' ${isChecked} onchange="calculateUpdateTotals()">
                    ${ev.name} - $${ev.price.toFixed(2)}
                </label>
            </div>
        `;
    });
}

function calculateUpdateTotals() {
    const selectedEvents = [];
    let baseTotal = 0;
    
    document.querySelectorAll('input[name="update_event"]:checked').forEach(chk => {
        const ev = JSON.parse(chk.value);
        selectedEvents.push(ev);
        baseTotal += parseFloat(ev.price);
    });

    const ttqLevy = 5.00;
    const discountAmount = parseFloat(currentReg.discountAmount || 0);
    let newFinalTotal = (baseTotal + ttqLevy) - discountAmount;
    if (newFinalTotal < 0) newFinalTotal = 0;
    
    document.getElementById('newTotalAmount').textContent = newFinalTotal.toFixed(2);
    
    const oldFinalTotal = parseFloat(currentReg.finalTotal || 0);
    const difference = newFinalTotal - oldFinalTotal;
    
    document.getElementById('differenceAmount').textContent = difference.toFixed(2);
    
    const warningEl = document.getElementById('refundWarning');
    const payBtn = document.getElementById('payDifferenceBtn');
    
    if (difference <= 0 && newFinalTotal !== oldFinalTotal) {
        warningEl.style.display = "block";
        payBtn.disabled = true;
    } else if (difference <= 0 && newFinalTotal === oldFinalTotal) {
        warningEl.style.display = "none";
        payBtn.disabled = true;
    } else {
        warningEl.style.display = "none";
        payBtn.disabled = false;
    }

    const partnerSection = document.getElementById('doublesPartnerSectionUpdate');
    const partnerInputs = document.getElementById('partnerInputsUpdate');
    partnerInputs.innerHTML = '';
    let needsPartner = false;

    selectedEvents.forEach(ev => {
        if (ev.name.toLowerCase().includes('doubles')) {
            needsPartner = true;
            let savedPartner = (currentReg.doublesPartners && currentReg.doublesPartners[ev.name]) ? currentReg.doublesPartners[ev.name] : "";
            partnerInputs.innerHTML += `
                <div class="form-group" style="margin-bottom: 10px;">
                    <label style="font-size: 13px;">Partner for ${ev.name}</label>
                    <input type="text" id="partner_update_${ev.id}" value="${savedPartner}" placeholder="Partner Name (or 'Partner Required')" required style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                </div>
            `;
        }
    });

    partnerSection.style.display = needsPartner ? 'block' : 'none';
}

async function processUpdateAndPay() {
    const selectedEvents = [];
    document.querySelectorAll('input[name="update_event"]:checked').forEach(chk => {
        selectedEvents.push(JSON.parse(chk.value));
    });

    const doublesPartners = {};
    selectedEvents.forEach(ev => {
        if (ev.name.toLowerCase().includes('doubles')) {
            const el = document.getElementById(`partner_update_${ev.id}`);
            if (el) doublesPartners[ev.name] = el.value;
        }
    });

    const payload = {
        reg_id: currentReg.id,
        events: selectedEvents,
        doublesPartners: doublesPartners
    };

    const btn = document.getElementById('payDifferenceBtn');
    btn.textContent = "Processing...";
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/registration/update-checkout`, {
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
        const response = await fetch(`${API_BASE}/registration/pay-balance`, {
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