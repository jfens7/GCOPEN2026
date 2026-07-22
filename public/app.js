const API_BASE = "/api";

window.toggleRcProfile = function() {
    const box = document.getElementById('neverPlayedBox');
    const input = document.getElementById('rcProfile');
    const btn = document.getElementById('lookupRcBtn');
    const results = document.getElementById('rcLookupResults');
    if (box.checked) {
        input.value = "Never Played";
        input.disabled = true;
        btn.disabled = true;
        if(results) results.innerHTML = "";
    } else {
        input.value = "";
        input.disabled = false;
        btn.disabled = false;
    }
};

// Elements
const form = document.getElementById('registrationForm');
const eventsTotalEl = document.getElementById('eventsTotal');
const discountAmountEl = document.getElementById('discountAmount');
const finalTotalEl = document.getElementById('finalTotal');
const discountCodeInput = document.getElementById('discountCode');
const applyDiscountBtn = document.getElementById('applyDiscountBtn');

const lookupTtaBtn = document.getElementById('lookupTtaBtn');
const autoFillByIdBtn = document.getElementById('autoFillByIdBtn');
const ttaLookupFeedback = document.getElementById('ttaLookupFeedback');
const ttaIdFeedback = document.getElementById('ttaIdFeedback');

const lookupRcBtn = document.getElementById('lookupRcBtn');
const rcProfileInput = document.getElementById('rcProfile');
const rcLookupResults = document.getElementById('rcLookupResults');

const dobInput = document.getElementById('dob');
const genderRadios = document.getElementsByName('gender');
const clubSelect = document.getElementById('clubSelect');
const clubOther = document.getElementById('clubOther');

let currentEvents = [];
let baseTotal = 0;
let discountValue = 0;
let validatedCode = "";
let currentRcRating = 0;
let currentRcId = "";
const TTQ_LEVY = 5.00;

// Master Events List for Admin Panel Editor
const masterEventsList = [
    {"id":10, "name":"Event #10: Under 17 Boy's Singles", "price":10},
    {"id":11, "name":"Event #11: Under 17 Girl's Singles", "price":10},
    {"id":12, "name":"Event #12: Under 15 Boy's Singles", "price":10},
    {"id":13, "name":"Event #13: Under 15 Girl's Singles", "price":10},
    {"id":16, "name":"Event #16: Under 11 Boy's Singles", "price":10},
    {"id":17, "name":"Event #17: Under 11 Girl's Singles", "price":10},
    {"id":8,  "name":"Event #8: Under 19 Boy's Singles", "price":10},
    {"id":9,  "name":"Event #9: Under 19 Girl's Singles", "price":10},
    {"id":14, "name":"Event #14: Under 13 Boy's Singles", "price":10},
    {"id":15, "name":"Event #15: Under 13 Girl's Singles", "price":10},
    {"id":3,  "name":"Event #3: Men's Open Doubles", "price":12},
    {"id":4,  "name":"Event #4: Women's Open Doubles", "price":12},
    {"id":6,  "name":"Event #6: Under 1700 Singles", "price":15},
    {"id":1,  "name":"Event #1: Men's Open Singles", "price":25},
    {"id":2,  "name":"Event #2: Women's Open Singles", "price":20},
    {"id":5,  "name":"Event #5: Para Open Singles", "price":10},
    {"id":7,  "name":"Event #7: Under 1400 Singles", "price":15},
    {"id":26, "name":"Event #26: Over 50 Men's Singles", "price":15},
    {"id":27, "name":"Event #27: Over 50 Women's Singles", "price":15},
    {"id":30, "name":"Event #30: Over 70 Men's Singles", "price":10},
    {"id":31, "name":"Event #31: Over 70 Women's Singles", "price":10},
    {"id":20, "name":"Event #20: Under 800 Singles", "price":12},
    {"id":24, "name":"Event #24: Over 40 Men's Singles", "price":15},
    {"id":25, "name":"Event #25: Over 40 Women's Singles", "price":15},
    {"id":21, "name":"Event #21: Open Rating Doubles", "price":10},
    {"id":33, "name":"Event #33: Veteran Women's Doubles", "price":10},
    {"id":34, "name":"Event #34: Veteran Men's Doubles", "price":10},
    {"id":19, "name":"Event #19: Under 1000 Singles", "price":15},
    {"id":22, "name":"Event #22: Over 30 Men's Singles", "price":15},
    {"id":23, "name":"Event #23: Over 30 Women's Singles", "price":15},
    {"id":28, "name":"Event #28: Over 60 Men's Singles", "price":12},
    {"id":29, "name":"Event #29: Over 60 Women's Singles", "price":12},
    {"id":32, "name":"Event #32: Over 80 Singles", "price":10},
    {"id":18, "name":"Event #18: Under 1200 Singles", "price":15}
];

// ==========================================
// CLUBS INITIALIZATION
// ==========================================
const australianClubs = [
    "Independent / None",
    "Gold Coast Table Tennis Association",
    "Brisbane Table Tennis Association",
    "Wynnum Table Tennis Association",
    "Moreton Bay Table Tennis Association",
    "Sunshine Coast Table Tennis",
    "Townsville Table Tennis Association",
    "Mackay Table Tennis Association",
    "Rockhampton Table Tennis Association",
    "Bundaberg Table Tennis Association",
    "Cairns Table Tennis Association",
    "Toowoomba Table Tennis Association",
    "Tweed Heads Table Tennis",
    "Sydney Indoor Table Tennis",
    "Table Tennis NSW",
    "Table Tennis Victoria",
    "Table Tennis SA",
    "Other"
];

if (clubSelect) {
    clubSelect.innerHTML = `<option value="">Select your club...</option>`;
    australianClubs.forEach(club => {
        clubSelect.innerHTML += `<option value="${club}">${club}</option>`;
    });
}

function toggleClubOther() {
    if (clubSelect && clubSelect.value === "Other") {
        clubOther.style.display = "block";
        clubOther.required = true;
    } else {
        clubOther.style.display = "none";
        clubOther.required = false;
    }
}

// ==========================================
// LOOKUP HANDLERS
// ==========================================
if (autoFillByIdBtn) {
    autoFillByIdBtn.addEventListener('click', async () => {
        const natId = document.getElementById('nationalId').value.trim();
        if (!natId) {
            alert("Please enter a National ID first.");
            return;
        }

        autoFillByIdBtn.innerText = "Loading...";
        autoFillByIdBtn.disabled = true;
        ttaIdFeedback.innerHTML = `<span style="color:var(--gctta-navy);">Fetching details from TTA...</span>`;

        try {
            const resp = await fetch(`${API_BASE}/national-id/lookup-by-id?id=${encodeURIComponent(natId)}`);
            const data = await resp.json();

            if (data.success) {
                document.getElementById('firstName').value = data.firstName;
                document.getElementById('lastName').value = data.lastName;
                if (data.dob) {
                    document.getElementById('dob').value = data.dob.length === 4 ? `01/01/${data.dob}` : data.dob;
                }
                ttaIdFeedback.innerHTML = `<span style="color:green; font-weight:bold;">✓ Details populated! Welcome ${data.firstName}.</span>`;
                if(typeof validateEligibility === "function") validateEligibility();
            } else {
                ttaIdFeedback.innerHTML = `<span style="color:red;">${data.error || "ID not found."}</span>`;
            }
        } catch (err) {
            ttaIdFeedback.innerHTML = `<span style="color:red;">Lookup failed. Please fill details manually.</span>`;
        }
        autoFillByIdBtn.innerText = "Auto-Fill Details";
        autoFillByIdBtn.disabled = false;
    });
}

if (lookupTtaBtn) {
    lookupTtaBtn.addEventListener('click', async () => {
        const firstName = document.getElementById('firstName').value.trim();
        const lastName = document.getElementById('lastName').value.trim();
        const fullName = `${firstName} ${lastName}`.trim();

        if (!fullName) {
            alert("Please enter First Name and Last Name first.");
            return;
        }

        lookupTtaBtn.innerText = "Searching...";
        lookupTtaBtn.disabled = true;
        ttaLookupFeedback.innerHTML = `<span style="color:var(--gctta-navy);">Searching TTA database...</span>`;

        try {
            const resp = await fetch(`${API_BASE}/national-id/search?name=${encodeURIComponent(fullName)}`);
            const data = await resp.json();

            if (data.success && data.nationalId) {
                document.getElementById('nationalId').value = data.nationalId;
                ttaLookupFeedback.innerHTML = `<span style="color:green; font-weight:bold;">✓ Found National ID: ${data.nationalId} (${data.state})</span>`;
            } else {
                ttaLookupFeedback.innerHTML = `<span style="color:red;">${data.error || "No ID found."}</span>`;
            }
        } catch (err) {
            ttaLookupFeedback.innerHTML = `<span style="color:red;">Lookup failed. Please enter ID manually.</span>`;
        }
        lookupTtaBtn.innerText = "Search TTA ID By Name";
        lookupTtaBtn.disabled = false;
    });
}

let rcPlayersData = [];

if (lookupRcBtn) {
    lookupRcBtn.addEventListener('click', async () => {
        const firstName = document.getElementById('firstName').value.trim();
        const lastName = document.getElementById('lastName').value.trim();
        const customQuery = rcProfileInput.value.trim();
        const query = customQuery || `${firstName} ${lastName}`.trim();

        if (!query) {
            alert("Please enter your name or an RC ID to search.");
            return;
        }

        lookupRcBtn.innerText = "Searching...";
        lookupRcBtn.disabled = true;
        rcLookupResults.innerHTML = "<span style='color:var(--gctta-navy);'>Fetching profiles from Ratings Central...</span>";

        try {
            const resp = await fetch(`${API_BASE}/ratings-central/search?query=${encodeURIComponent(query)}`);
            const data = await resp.json();

            if (data.players && data.players.length > 0) {
                rcPlayersData = data.players;
                let html = `<div class="rc-grid">`;
                data.players.forEach((p, index) => {
                    html += `
                    <div class="rc-card" id="rcCard_${index}" onclick="selectRcProfile(${index})">
                        <h4>${p.name}</h4>
                        <p><strong>Rating:</strong> ${p.rating}</p>
                        <p><strong>RC ID:</strong> ${p.id}</p>
                        <p><small>Last: ${p.lastEvent}</small></p>
                    </div>`;
                });
                html += `</div>`;
                rcLookupResults.innerHTML = html;
            } else {
                rcLookupResults.innerHTML = `<span style="color:red;">No Ratings Central profile found.</span>`;
            }
        } catch (err) {
            rcLookupResults.innerHTML = `<span style="color:red;">Lookup failed.</span>`;
        }
        lookupRcBtn.innerText = "FIND PROFILE";
        lookupRcBtn.disabled = false;
    });
}

function selectRcProfile(index) {
    document.querySelectorAll('.rc-card').forEach(el => el.classList.remove('selected'));
    document.getElementById(`rcCard_${index}`).classList.add('selected');
    
    const selectedPlayer = rcPlayersData[index];
    rcProfileInput.value = `${selectedPlayer.name} (ID: ${selectedPlayer.id})`;
    currentRcRating = selectedPlayer.rating;
    currentRcId = selectedPlayer.id; // Store strictly for backend separation
    
    if(typeof validateEligibility === "function") validateEligibility();
}

// ==========================================
// VALIDATION & DOUBLES LOGIC
// ==========================================
const eventRules = {
    8: { type: 'age', maxAge: 19, gender: 'Male' },
    9: { type: 'age', maxAge: 19, gender: 'Female' },
    10: { type: 'age', maxAge: 17, gender: 'Male' },
    11: { type: 'age', maxAge: 17, gender: 'Female' },
    12: { type: 'age', maxAge: 15, gender: 'Male' },
    13: { type: 'age', maxAge: 15, gender: 'Female' },
    14: { type: 'age', maxAge: 13, gender: 'Male' },
    15: { type: 'age', maxAge: 13, gender: 'Female' },
    16: { type: 'age', maxAge: 11, gender: 'Male' },
    17: { type: 'age', maxAge: 11, gender: 'Female' },
    22: { type: 'age', minAge: 30, gender: 'Male' },
    23: { type: 'age', minAge: 30, gender: 'Female' },
    24: { type: 'age', minAge: 40, gender: 'Male' },
    25: { type: 'age', minAge: 40, gender: 'Female' },
    26: { type: 'age', minAge: 50, gender: 'Male' },
    27: { type: 'age', minAge: 50, gender: 'Female' },
    28: { type: 'age', minAge: 60, gender: 'Male' },
    29: { type: 'age', minAge: 60, gender: 'Female' },
    30: { type: 'age', minAge: 70, gender: 'Male' },
    31: { type: 'age', minAge: 70, gender: 'Female' },
    32: { type: 'age', minAge: 80 },
    6: { type: 'rating', maxRating: 1700 },
    7: { type: 'rating', maxRating: 1400 },
    18: { type: 'rating', maxRating: 1200 },
    19: { type: 'rating', maxRating: 1000 },
    20: { type: 'rating', maxRating: 800 },
    1: { gender: 'Male' },
    2: { gender: 'Female' },
    3: { gender: 'Male' },
    4: { gender: 'Female' },
    33: { gender: 'Female'},
    34: { gender: 'Male'}
};

const doublesEventIds = [3, 4, 21, 33, 34];

function validateEligibility() {
    const dobStr = dobInput.value.trim();
    const yearMatches = dobStr.match(/\d{4}/);
    const birthYear = yearMatches ? parseInt(yearMatches[0]) : 0;
    const ageIn2026 = birthYear > 0 ? (2026 - birthYear) : 0; 
    
    let selectedGender = "";
    genderRadios.forEach(r => { if(r.checked) selectedGender = r.value; });

    const radios = document.querySelectorAll('input[type="radio"][name^="sat_"], input[type="radio"][name^="sun_"]');
    
    radios.forEach(radio => {
        if (!radio.value) return; 
        const eventData = JSON.parse(radio.value);
        const rules = eventRules[eventData.id];
        let disabled = false;
        let reason = "";

        if (rules) {
            // STRICT GENDER LOCKING
            if (rules.gender && rules.gender !== selectedGender && selectedGender !== "") {
                disabled = true;
                reason = `(Requires ${rules.gender})`;
            }
            if (rules.maxAge && ageIn2026 > rules.maxAge && ageIn2026 > 0) {
                disabled = true;
                reason = `(Too old - Age ${ageIn2026})`;
            }
            if (rules.minAge && ageIn2026 < rules.minAge && ageIn2026 > 0) {
                disabled = true;
                reason = `(Too young - Age ${ageIn2026})`;
            }
            if (rules.maxRating && currentRcRating > rules.maxRating) {
                disabled = true;
                reason = `(Your Rating ${currentRcRating} > Max ${rules.maxRating})`;
            }
        }

        const label = radio.parentElement;
        
        if (disabled) {
            radio.checked = false;
            radio.disabled = true; 
            label.style.color = "#ccc";
            label.style.pointerEvents = "none"; // Hard lock to prevent bypass
            label.style.textDecoration = "line-through";
            if (!label.innerHTML.includes("reason-text")) {
                label.innerHTML += ` <span class="reason-text" style="color:red; font-size: 12px; text-decoration: none;">${reason}</span>`;
            }
        } else {
            radio.disabled = false;
            label.style.color = "#333";
            label.style.pointerEvents = "auto";
            label.style.textDecoration = "none";
            const reasonSpan = label.querySelector('.reason-text');
            if (reasonSpan) reasonSpan.remove();
        }
    });
    handleDoublesPartners();
}

if(dobInput) dobInput.addEventListener('input', validateEligibility);
genderRadios.forEach(r => r.addEventListener('change', validateEligibility));

function handleDoublesPartners() {
    const partnerSection = document.getElementById('doublesPartnerSection');
    const partnerInputs = document.getElementById('partnerInputs');
    
    let needsPartner = false;
    const radios = document.querySelectorAll('input[type="radio"][name^="sat_"]:checked, input[type="radio"][name^="sun_"]:checked');
    
    const existingVals = {};
    document.querySelectorAll('[id^="partner_"]').forEach(inp => {
        existingVals[inp.id] = inp.value;
    });

    partnerInputs.innerHTML = "";
    
    radios.forEach(radio => {
        if (radio.value) {
            const eventData = JSON.parse(radio.value);
            if (doublesEventIds.includes(eventData.id)) {
                needsPartner = true;
                const prevValue = existingVals[`partner_${eventData.id}`] || '';
                partnerInputs.innerHTML += `
                    <div style="margin-top: 10px; padding: 10px; background: white; border-radius: 4px; border: 1px solid #ccc;">
                        <label style="font-size:12px; font-weight:bold; color:var(--gctta-navy);">Partner for ${eventData.name}:</label>
                        <div class="form-row" style="margin-top: 5px; gap: 10px;">
                            <input type="text" id="partner_${eventData.id}" value="${prevValue}" placeholder="Enter Partner's Name" required style="flex: 2; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
                            <button type="button" class="btn-secondary-small" onclick="document.getElementById('partner_${eventData.id}').value='Partner Required'" style="flex: 1; font-size: 13px; padding: 8px;">Need Partner</button>
                        </div>
                    </div>
                `;
            }
        }
    });

    partnerSection.style.display = needsPartner ? "block" : "none";
}

// ==========================================
// FORM SUBMISSION & REGISTRATION
// ==========================================
if (form) {
    form.addEventListener('change', (e) => {
        if (e.target.type === 'radio') {
            handleDoublesPartners();
            calculateTotals();
        }
    });

    if (applyDiscountBtn) {
        applyDiscountBtn.addEventListener('click', async () => {
            const code = discountCodeInput.value.trim().toUpperCase();
            if (!code) return;
            applyDiscountBtn.innerText = "...";
            try {
                const response = await fetch(`${API_BASE}/validate-discount/${code}`);
                const data = await response.json();
                if (data.valid) {
                    discountValue = data.discountAmount;
                    validatedCode = code;
                    alert(`Discount Code Applied! $${discountValue.toFixed(2)} off.`);
                } else {
                    discountValue = 0;
                    validatedCode = "";
                    alert("Invalid or already used code.");
                }
            } catch(err) {
                alert("Error validating code.");
            }
            applyDiscountBtn.innerText = "Verify";
            calculateTotals();
        });
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        await window.submitRegistration(false);
    });

    window.submitRegistration = async function(payLater = false) {
        currentEvents = [];
        const radios = document.querySelectorAll('input[type="radio"][name^="sat_"]:checked, input[type="radio"][name^="sun_"]:checked');
        radios.forEach(radio => {
            if (radio.value) currentEvents.push(JSON.parse(radio.value));
        });

        if(currentEvents.length === 0) {
            alert("Please select at least one event!");
            return;
        }

        const doublesPartners = {};
        let missingPartner = false;
        currentEvents.forEach(ev => {
            if (doublesEventIds.includes(ev.id)) {
                const pName = document.getElementById(`partner_${ev.id}`).value.trim();
                if (!pName) missingPartner = true;
                doublesPartners[ev.name] = pName;
            }
        });

        if (missingPartner) {
            alert("Please fill out your doubles partner details (or click 'Need Partner').");
            return;
        }
        
        let finalClub = clubSelect.value;
        if (finalClub === "Other") finalClub = clubOther.value;

        const payload = {
            player: {
                firstName: document.getElementById('firstName').value,
                lastName: document.getElementById('lastName').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                nationalId: document.getElementById('nationalId').value,
                dob: document.getElementById('dob').value,
                club: finalClub,
                rcProfile: document.getElementById('rcProfile').value,
                rcId: currentRcId // Explicitly sent for GSheet separation
            },
            events: currentEvents,
            doublesPartners: doublesPartners,
            discountCode: validatedCode,
            payLater: payLater
        };

        const btn = document.getElementById('checkoutBtn');
        const savePayLaterBtn = document.getElementById('savePayLaterBtn');
        btn.innerText = "Processing...";
        btn.disabled = true;
        if (savePayLaterBtn) savePayLaterBtn.disabled = true;
        
        try {
            const response = await fetch(`${API_BASE}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            
            if (data.error) {
                alert(data.error);
                btn.innerText = "PROCEED TO SECURE PAYMENT";
                btn.disabled = false;
                if (savePayLaterBtn) savePayLaterBtn.disabled = false;
            } else if (data.url) {
                window.location.href = data.url;
            }
        } catch (err) {
            alert("Network error.");
            btn.innerText = "PROCEED TO SECURE PAYMENT";
            btn.disabled = false;
            if (savePayLaterBtn) savePayLaterBtn.disabled = false;
        }
    };
}

function calculateTotals() {
    baseTotal = 0;
    const radios = document.querySelectorAll('input[type="radio"][name^="sat_"]:checked, input[type="radio"][name^="sun_"]:checked');
    
    radios.forEach(radio => {
        if (radio.value) {
            const eventData = JSON.parse(radio.value);
            baseTotal += eventData.price;
        }
    });

    let final = (baseTotal + TTQ_LEVY) - discountValue;
    if (final < 0) final = 0;

    if(eventsTotalEl) eventsTotalEl.innerText = baseTotal.toFixed(2);
    if(discountAmountEl) discountAmountEl.innerText = discountValue.toFixed(2);
    if(finalTotalEl) finalTotalEl.innerText = final.toFixed(2);
}

// ==========================================
// ADMIN DASHBOARD
// ==========================================
let allRegistrations = [];

async function loadAdminData() {
    const tableBody = document.querySelector("#adminTable tbody");
    if (!tableBody) return;

    try {
        const response = await fetch(`${API_BASE}/admin/registrations`);
        const registrations = await response.json();
        allRegistrations = registrations; // store in memory for editing
        
        tableBody.innerHTML = "";
        registrations.forEach(reg => {
            const eventNames = reg.events.map(e => e.name).join(", ");
            const partnersStr = Object.entries(reg.doublesPartners || {}).map(([ev, p]) => `${ev}: ${p}`).join('<br>');
            const badgeClass = reg.paymentStatus.toLowerCase() === 'paid' ? 'paid' : 'pending';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${reg.player.firstName} ${reg.player.lastName}</td>
                <td>${reg.player.email}</td>
                <td>${eventNames}</td>
                <td><small>${partnersStr}</small></td>
                <td>$${reg.finalTotal.toFixed(2)}</td>
                <td><span class="badge ${badgeClass}">${reg.paymentStatus}</span></td>
                <td>
                    <button class="lookup-btn" onclick="openEditModal('${reg.id}')" style="padding: 5px 10px; font-size:12px; margin-bottom: 5px; width:100%;">Edit Record</button>
                    <button class="lookup-btn" onclick="waiveFee('${reg.id}')" style="padding: 5px 10px; font-size:12px; width: 100%; margin-bottom: 5px; background-color: #64748B;">Waive Fee</button>
                    <button class="lookup-btn" onclick="deleteRegistration('${reg.id}')" style="padding: 5px 10px; font-size:12px; width: 100%; background-color: #DC2626;">Delete</button>
                </td>
            `;
            tableBody.appendChild(tr);
        });
    } catch(err) {
        console.error("Error loading admin data", err);
    }
}

// Edit Modal Handling
function openEditModal(regId) {
    const reg = allRegistrations.find(r => r.id === regId);
    if (!reg) return;

    if (document.getElementById('playerProfileDetails')) {
        const p = reg.player;
        document.getElementById('playerProfileDetails').innerHTML = `
            <div><strong>DOB:</strong> ${p.dob || 'N/A'}</div>
            <div><strong>Phone:</strong> ${p.phone || 'N/A'}</div>
            <div><strong>Club:</strong> ${p.club || 'N/A'}</div>
            <div><strong>TTA ID:</strong> ${p.nationalId || 'N/A'}</div>
            <div><strong>Ratings Central ID:</strong> ${p.rcId || 'N/A'}</div>
            <div><strong>Ratings Central Profile:</strong> ${p.rcProfile ? `<a href="${p.rcProfile}" target="_blank">View</a>` : 'N/A'}</div>
        `;
    }

    document.getElementById('editRegId').value = reg.id;
    document.getElementById('editFirstName').value = reg.player.firstName;
    document.getElementById('editLastName').value = reg.player.lastName;
    document.getElementById('editEmail').value = reg.player.email;
    document.getElementById('editTotal').value = reg.finalTotal;
    document.getElementById('editStatus').value = reg.paymentStatus;
    if (document.getElementById('editBalance')) {
        document.getElementById('editBalance').value = reg.balanceDue || 0;
    }
    
    if (document.getElementById('copyPaymentLinkBtn')) {
        document.getElementById('copyPaymentLinkBtn').onclick = () => {
            const url = new URL('/update.html', window.location.origin);
            url.searchParams.set('email', reg.player.email);
            url.searchParams.set('dob', reg.player.dob);
            navigator.clipboard.writeText(url.toString()).then(() => {
                alert("Payment/Update link copied to clipboard!");
            });
        };
    }

    // Populate Events Checkboxes (Allows Bypassing Rules)
    const eventsList = document.getElementById('editEventsList');
    eventsList.innerHTML = "";
    const regEventIds = reg.events.map(e => e.id);
    
    masterEventsList.forEach(ev => {
        const isChecked = regEventIds.includes(ev.id) ? "checked" : "";
        eventsList.innerHTML += `
            <div style="margin-bottom: 5px;">
                <label style="cursor: pointer; font-weight: normal; font-size: 13px;">
                    <input type="checkbox" name="edit_event" value='${JSON.stringify(ev)}' ${isChecked}>
                    ${ev.name}
                </label>
            </div>
        `;
    });

    document.getElementById('editModal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('editModal').style.display = 'none';
}

async function saveRegistrationEdit() {
    const regId = document.getElementById('editRegId').value;
    const fName = document.getElementById('editFirstName').value;
    const lName = document.getElementById('editLastName').value;
    const email = document.getElementById('editEmail').value;
    const total = parseFloat(document.getElementById('editTotal').value);
    const status = document.getElementById('editStatus').value;
    const balanceEl = document.getElementById('editBalance');
    let balance = balanceEl ? parseFloat(balanceEl.value) : 0;
    if (isNaN(balance)) balance = 0;

    const checkedEvents = [];
    document.querySelectorAll('input[name="edit_event"]:checked').forEach(chk => {
        checkedEvents.push(JSON.parse(chk.value));
    });

    const payload = {
        "player.firstName": fName,
        "player.lastName": lName,
        "player.email": email,
        "finalTotal": total,
        "paymentStatus": status,
        "balanceDue": balance,
        "events": checkedEvents
    };

    try {
        await fetch(`${API_BASE}/admin/registrations/${regId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        alert("Registration successfully updated! Google Sheets in sync.");
        closeEditModal();
        loadAdminData();
        loadStats();
    } catch(err) {
        alert("Failed to update registration.");
    }
}

async function deleteRegistration(regId = null) {
    if (typeof regId !== 'string') {
        regId = document.getElementById('editRegId').value;
    }
    if (!confirm("Are you sure you want to permanently delete this registration? This action cannot be undone and will remove it from the database and Google Sheets.")) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/admin/registrations/${regId}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            alert("Registration deleted successfully.");
            closeEditModal();
            loadAdminData();
            loadStats();
        } else {
            alert("Failed to delete registration.");
        }
    } catch (err) {
        alert("Error deleting registration.");
        console.error(err);
    }
}

async function waiveFee(regId) {
    if(confirm("Are you sure you want to waive the fee and mark this as Paid?")) {
        await fetch(`${API_BASE}/admin/registrations/${regId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ finalTotal: 0, paymentStatus: 'Paid' })
        });
        alert("Fee waived and updated.");
        loadAdminData();
        loadStats();
    }
}

// Zermelo CSV Export
function exportZermeloCSV() {
    fetch(`${API_BASE}/admin/registrations`)
        .then(res => res.json())
        .then(data => {
            let csvContent = "data:text/csv;charset=utf-8,";
            // Zermelo optimal headers
            csvContent += "FirstName,LastName,NationalID,RatingsCentralID,Club,Events\n";
            
            data.forEach(reg => {
                const fName = `"${reg.player.firstName}"`;
                const lName = `"${reg.player.lastName}"`;
                const natId = `"${reg.player.nationalId || ''}"`;
                const rcId = `"${reg.player.rcId || ''}"`;
                
                let club = reg.player.club || '';
                if(club === 'Independent / None') club = 'None';
                club = `"${club}"`;
                
                const events = `"${reg.events.map(e => e.name).join('; ')}"`;
                
                csvContent += [fName, lName, natId, rcId, club, events].join(",") + "\n";
            });
            
            const encodedUri = encodeURI(csvContent);
            const link = document.createElement("a");
            link.setAttribute("href", encodedUri);
            link.setAttribute("download", "GCOpen2026_Zermelo_Export.csv");
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
}

// Discount & Stats Handlers
async function loadDiscountCodes() {
    const tableBody = document.querySelector("#discountTable tbody");
    if (!tableBody) return;

    try {
        const response = await fetch(`${API_BASE}/admin/discount-codes`);
        const codes = await response.json();
        
        tableBody.innerHTML = "";
        codes.forEach(c => {
            const badgeClass = c.used ? 'pending' : 'paid'; 
            const statusText = c.used ? 'Used' : 'Active';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${c.code}</strong></td>
                <td>$${c.discountAmount.toFixed(2)}</td>
                <td><span class="badge ${badgeClass}">${statusText}</span></td>
            `;
            tableBody.appendChild(tr);
        });
    } catch(err) {
        console.error("Error loading discount codes", err);
    }
}

async function generateCode() {
    const amount = document.getElementById('newDiscountAmount').value;
    try {
        await fetch(`${API_BASE}/admin/discount-codes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: amount })
        });
        alert("New unique discount code generated!");
        loadDiscountCodes();
    } catch(err) {
        alert("Failed to generate code.");
    }
}

async function loadStats() {
    try {
        const res = await fetch('/api/admin/stats');
        const data = await res.json();
        const revEl = document.getElementById('statRevenue');
        if (revEl) revEl.innerText = `$${data.totalRevenue.toFixed(2)}`;
        const playersEl = document.getElementById('statPlayers');
        if (playersEl) playersEl.innerText = data.totalPlayers;
        const pendingEl = document.getElementById('statPending');
        if (pendingEl) pendingEl.innerText = data.pendingPayments;
    } catch (err) { console.error(err); }
}
