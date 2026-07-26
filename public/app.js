const API_BASE = "/api";

document.addEventListener("DOMContentLoaded", () => {
    // --- THREE STRIKES STRIPE TRACKING ---
    const urlParams = new URLSearchParams(window.location.search);
    let attempts = parseInt(localStorage.getItem('gco_payment_attempts') || '0');

    if (urlParams.has('canceled')) {
        attempts++;
        localStorage.setItem('gco_payment_attempts', attempts);
        
        // Clean the URL so refreshing doesn't add fake strikes
        window.history.replaceState({}, document.title, window.location.pathname);
        
        if (attempts < 3) {
            alert(`Payment cancelled or failed. You have ${3 - attempts} attempt(s) remaining before manual payment is unlocked.`);
        }
    }

    // If they have 3 or more strikes, unhide the Pay Later box
    if (attempts >= 3) {
        const payLaterContainer = document.getElementById('payLaterContainer');
        if(payLaterContainer) payLaterContainer.style.display = 'block';
    }
});

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
let discountType = "dollar";
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
  "Centenary Table Tennis Club",
  "Ipswich Table Tennis Association",
  "Crows Nest and District Table Tennis Association",
  "Gatton Table Tennis Association",
  "Noosa Table Tennis Club",
  "University of Queensland Table Tennis Club",
  "Maryborough Table Tennis & Pickleball",
  "Star Table Tennis Association",
  "Table Tennis Society",
  "Yvonne Table Tennis Academy",
  "ACDMA Table Tennis Club",
  "Albury Wodonga Table Tennis Association",
  "Apex Table Tennis Centre",
  "Ararat/Armenian Table Tennis Club",
  "Armidale Table Tennis Club",
  "Ashfield Table Tennis Club",
  "Australian Table Tennis Academy",
  "Australian Table Tennis Promotion Association",
  "Bathurst District Table Tennis Association",
  "Bavpast Social Table Tennis Club",
  "Bega Table Tennis Club",
  "Bermagui Table Tennis Club",
  "Blacktown Workers Table Tennis Club",
  "Blayney Table Tennis",
  "Bowral Table Tennis Association",
  "Byron Bay Table Tennis Club",
  "Cabarita Beach Table Tennis Club",
  "Cabra-Vale Diggers Club",
  "Canterbury Leagues Club",
  "Central Coast Table Tennis Club",
  "Chatswood Table Tennis Club",
  "Cherrybrook Table Tennis Club",
  "Coffs Harbour Over 50s Table Tennis Club",
  "Coffs Table Tennis Club",
  "Con's Table Tennis Academy",
  "Cronulla RSL",
  "CrossCourt Table Tennis Hub",
  "Dooley's Table Tennis Club",
  "E.L.I.T.E. Table Tennis Club",
  "EH Table Tennis Club",
  "Epping Table Tennis Club",
  "Fairfield PCYC",
  "Far North Coast Table Tennis Association",
  "Far South Coast Table Tennis Group",
  "Forestville Table Tennis Club",
  "Georges River Association Table Tennis Club",
  "Gina Table Tennis Academy",
  "Goulburn Table Tennis Association",
  "Hong Kong University Alumni Association NSW Chapter",
  "Hornsby RSL Table Tennis Club",
  "Howlong Table Tennis Club",
  "Hunters Hill Glades Table Tennis Group",
  "Illawarra District Table Tennis Association",
  "Inh Le Table Tennis Academy",
  "Inter-University Table Tennis Association",
  "J & B Sports Club",
  "JJW Table Tennis Club",
  "Katoomba Table Tennis Club",
  "Kempsey Macleay Table Tennis Club",
  "Kiama Table Tennis Club",
  "Kim's Training Centre",
  "Kogarah Table Tennis Club",
  "KTTA Juniors Training Centre",
  "Lane Cove Table Tennis Group",
  "Lithgow Table Tennis Association",
  "Macquarie University Table Tennis Club",
  "Maitland Social Table Tennis Club",
  "Manning Table Tennis Club",
  "Mounties Table Tennis Club",
  "MTTC Table Tennis",
  "Nambucca Heads Table Tennis Club",
  "Nepean District Table Tennis Association",
  "Newcastle PCYC Table Tennis Club",
  "North Shore Table Tennis Academy",
  "Norths Table Tennis Club",
  "Norwest Table Tennis Club",
  "NSW Country Table Tennis League",
  "NSW Insurance Officers Table Tennis Association",
  "NSW Veterans Table Tennis Association",
  "Opal Grand Table Tennis Club",
  "Orange Table Tennis Association",
  "Paul Zhao Table Tennis Academy",
  "Peter Masen Table Tennis Academy",
  "Ping Pong HQ Kingsgrove",
  "Port Macquarie Table Tennis Club",
  "Pymble Table Tennis Club",
  "Robertson Table Tennis Association",
  "RTTC Table Tennis Academy",
  "South Hurstville",
  "South Tweed Sports Table Tennis Club",
  "St George & Sutherland Shire Active Seniors",
  "St George & Sutherland Shire Table Tennis Association",
  "Stars Centre",
  "Sydney Northern Districts Table Tennis Association",
  "Sydney Sports Club",
  "Sydney Suburban Sports Club Incorporated",
  "Sydney Table Tennis Club",
  "Sydney Upper North Shore Table Tennis Association",
  "Table Tennis ACT",
  "Table Tennis Canberra North Club",
  "Table Tennis NSW Umpires & Referees Association",
  "Table Tennis Western Sydney",
  "Tamworth Table Tennis Club",
  "Terrey Hills Table Tennis Club",
  "The Country Club Table Tennis Club",
  "The Elanora Table Tennis Centre",
  "Vietnamese Australian Table Tennis Association",
  "Vivian's Table Tennis Academy",
  "Wagga Wagga Table Tennis Club",
  "Wentworthville Leagues Table Tennis Club",
  "Willoughby Table Tennis Club",
  "Wollondilly Table Tennis Association",
  "World Table Tennis Centre",
  "Xpong Table Tennis Club",
  "Bairnsdale & District Table Tennis Association/KeenAgers",
  "Ballarat Table Tennis Association",
  "Balwyn United Table Tennis Club",
  "Bellarine Keenagers Table Tennis Club",
  "Bellarine Table Tennis Club",
  "Bendigo & District Table Tennis Association",
  "CH Table Tennis",
  "Coburg Table Tennis Club",
  "Croydon & Districts Table Tennis Association",
  "Daylesford Table Tennis Association",
  "Deniliquin Table Tennis Club",
  "Diamond Valley Table Tennis Association",
  "Eastern Suburbs & Churches Table Tennis Association",
  "Geelong Table Tennis Association",
  "Gisborne District Table Tennis Association",
  "Greater Dandenong Table Tennis Association",
  "Hamilton Table Tennis Association",
  "Horsham Table Tennis Association",
  "ICC Academy",
  "Kyabram Youth Club",
  "Lakes Entrance Keenagers",
  "Leongatha Table Tennis Association",
  "LOOPS powered by HWATT",
  "Maccabi Table Tennis Club (VIC)",
  "Manningham Table Tennis Club",
  "Melbourne Veterans Table Tennis Association",
  "Melton Table Tennis Association",
  "Miao's Table Tennis Academy",
  "Moe/Newborough Keen-agers",
  "Monbulk Table Tennis Association",
  "Mornington Peninsula & Frankston City Table Tennis Association",
  "Officer City Soccer Club",
  "Peak Agility Table Tennis",
  "Peter's Table Tennis Academy",
  "Portland Table Tennis Association",
  "Sale Keenagers Table Tennis Club",
  "Scorpio Table Tennis Academy",
  "Shepparton Table Tennis Association",
  "South Eastern Table Tennis Association",
  "St Kilda Cricket Table Tennis Club",
  "Sunbury & District Table Tennis Association",
  "Sunraysia Table Tennis Association",
  "Sunshine & District Table Tennis Association",
  "Swan Hill Table Tennis Association",
  "Table Tennis Victoria",
  "Terang Table Tennis Association",
  "The Disruptor Club",
  "Traralgon Table Tennis Association",
  "Triangle Table Tennis",
  "Vietnamese Table Tennis Association",
  "Wangaratta Table Tennis Association",
  "Warracknabeal Table Tennis Association",
  "Warrnambool Table Tennis Association",
  "Werribee Table Tennis Association",
  "Western Table Tennis Club",
  "Wonthaggi Table Tennis Association",
  "Yarra Table Tennis Club",
  "Yarrawonga/Mulwala Table Tennis Association",
  "Albert Park Club",
  "Anthony's Table Tennis Academy",
  "Deakin University Table Tennis Club",
  "Melbourne Lakeside Table Tennis",
  "Melbourne University Table Tennis Club",
  "Monash Caulfield Table Tennis Club",
  "Monash Clayton Table Tennis Club",
  "Old Melburnians Table Tennis",
  "RMIT Table Tennis Club",
  "Swinburne Table Tennis Club",
  "Trafalgar Ping Pong Kings",
  "Victoria University Table Tennis Club",
  "Hopetoun Table Tennis Club",
  "Warracknabeal Table Tennis",
  "Adelaide Table Tennis Club",
  "Barossa & Light Table Tennis Association",
  "Brighton District Table Tennis Club",
  "Campbelltown City Table Tennis (HEATT)",
  "Copper Coast Table Tennis Association",
  "German Table Tennis Club",
  "Great Southern Table Tennis Association",
  "Jamestown Table Tennis Association",
  "Mount Gambier Table Tennis Association",
  "Murray Bridge & Districts Table Tennis Association",
  "North East Hills Table Tennis Association",
  "Payneham Table Tennis Academy",
  "Port Lincoln Table Tennis Association",
  "Port Pirie Table Tennis Club",
  "Renmark Table Tennis Association",
  "South Australian Table Tennis Officiating Council",
  "Southern Table Tennis",
  "Vietnamese Friendship Table Tennis Club",
  "Whyalla Table Tennis Association",
  "Wilmington Table Tennis Club Inc",
  "Woodville District Table Tennis Club",
  "Inman Valley Table Tennis Club",
  "South Coast Seniors",
  "Ebenezer Table Tennis Club",
  "Eden Valley Table Tennis Club",
  "Light Pass Table Tennis Club",
  "Tanunda Table Tennis Club",
  "Albany Table Tennis Club",
  "Armadale Table Tennis Club",
  "Black Swan Table Tennis Club",
  "Denmark Table Tennis Club",
  "Esperance Table Tennis Club",
  "Fremantle Table Tennis Club - Bicton",
  "Fremantle Table Tennis Club - Samson",
  "Geographe Bay Table Tennis Club",
  "Geraldton Table Tennis Club",
  "Great Wall Table Tennis Club",
  "Hammond Table Tennis Club",
  "Hot Shot Table Tennis Club",
  "Kingsway Table Tennis Club",
  "Mandurah Table Tennis Club",
  "Melville Seniors Table Tennis Group",
  "Morley Table Tennis Club",
  "Scarborough Table Tennis Club",
  "Sun Table Tennis Club",
  "Swans Table Tennis Club",
  "Table Tennis Western Australia",
  "Top Spins Table Tennis Club",
  "Table Tennis NSW",
  "Table Tennis SA",
  "Table Tennis WA",
  "Table Tennis NT",
  "Other",
  "ya Mum",
  "Naoya's Mum",
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
                
                // DOB Fix: Force manual entry if only year is provided
                if (data.dob && data.dob.length === 4) {
                    document.getElementById('dob').value = ""; 
                    alert(`We found your birth year (${data.dob}), but please manually enter your exact Date of Birth (DD/MM/YYYY).`);
                } else if (data.dob) {
                    document.getElementById('dob').value = data.dob;
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
    
    // Standard Juniors age rule
    const ageIn2026 = birthYear > 0 ? (2026 - birthYear) : 0; 
    
    // Veteran specific rule - eligible for age bracket they turn in 2027
    const ageIn2027 = birthYear > 0 ? (2027 - birthYear) : 0; 
    
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
            if (rules.minAge && ageIn2027 < rules.minAge && ageIn2027 > 0) {
                disabled = true;
                reason = `(Too young - Age in 2027: ${ageIn2027})`;
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
            label.style.pointerEvents = "none"; 
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
                    discountType = data.discountType || 'dollar';
                    validatedCode = code;
                    if (discountType === 'percent') {
                        alert(`Discount Code Applied! ${discountValue}% off.`);
                    } else {
                        alert(`Discount Code Applied! $${discountValue.toFixed(2)} off.`);
                    }
                } else {
                    discountValue = 0;
                    discountType = 'dollar';
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

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        
        currentEvents = [];
        const radios = document.querySelectorAll('input[type="radio"][name^="sat_"]:checked, input[type="radio"][name^="sun_"]:checked');
        radios.forEach(radio => {
            if (radio.value) currentEvents.push(JSON.parse(radio.value));
        });

        if(currentEvents.length === 0) {
            alert("Please select at least one event!");
            return;
        }

        let missingPartner = false;
        currentEvents.forEach(ev => {
            if (doublesEventIds.includes(ev.id)) {
                const pName = document.getElementById(`partner_${ev.id}`).value.trim();
                if (!pName) missingPartner = true;
            }
        });

        if (missingPartner) {
            alert("Please fill out your doubles partner details (or click 'Need Partner').");
            return;
        }

        window.openTcModal(); 
    });

    window.submitRegistration = async function() {
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

        let selectedGender = "N/A";
        const genderRadios = document.getElementsByName('gender');
        genderRadios.forEach(r => { if(r.checked) selectedGender = r.value; });

        const payLaterInput = document.getElementById('payLaterCheckbox');
        const isPayLater = payLaterInput ? payLaterInput.checked : false;

        const payload = {
            player: {
                firstName: document.getElementById('firstName').value,
                lastName: document.getElementById('lastName').value,
                email: document.getElementById('email').value,
                phone: document.getElementById('phone').value,
                nationalId: document.getElementById('nationalId').value,
                dob: document.getElementById('dob').value,
                gender: selectedGender, 
                club: finalClub,
                rcProfile: document.getElementById('rcProfile').value,
                rcId: currentRcId 
            },
            events: currentEvents,
            doublesPartners: doublesPartners,
            discountCode: validatedCode,
            payLater: isPayLater
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

    let computedDiscount = 0;
    if (discountType === 'percent') {
        computedDiscount = (baseTotal + TTQ_LEVY) * (discountValue / 100.0);
    } else {
        computedDiscount = discountValue;
    }

    let final = (baseTotal + TTQ_LEVY) - computedDiscount;
    if (final < 0) final = 0;

    if(eventsTotalEl) eventsTotalEl.innerText = baseTotal.toFixed(2);
    if(discountAmountEl) discountAmountEl.innerText = computedDiscount.toFixed(2);
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
        allRegistrations = registrations; 
        
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