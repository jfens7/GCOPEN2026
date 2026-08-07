import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import os

# Connect to your Firebase (Ensure the JSON key is in the same folder)
cred_path = "gc-open-2026-firebase-adminsdk-fbsvc-efd2385c84.json"
if not os.path.exists(cred_path):
    print(f"Error: Could not find {cred_path}")
    exit(1)

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

def create_players(names):
    return [{"name": name, "wins": 0, "losses": 0, "pts": 0, "advance": False} for name in names]

def blank_bracket(size):
    matches = []
    for _ in range(size):
        matches.append({"p1": "TBD", "s1": "0", "p2": "TBD", "s2": "0", "winner": 0})
    return matches

# ==========================================
# EXTRACTED PDF DATA PAYLOAD
# ==========================================
draws_data = [
    {
        "eventName": "Event #1: Men's Open Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Hayden Green"])},
            {"name": "Group 2", "players": create_players(["Naoya Yamamoto", "Tsz Kin Andersen Kwok", "Muhammad Ihsan-Hess"])},
            {"name": "Group 3", "players": create_players(["David Lu", "Jeffrey Chen", "Juan Arias"])},
            {"name": "Group 4", "players": create_players(["Shanith Jayamaha", "Pranav Prasad", "Jakob Fensom"])},
            {"name": "Group 5", "players": create_players(["Seref Bakanay", "Praveen Gunawardena", "Cohen McMaster"])},
            {"name": "Group 6", "players": create_players(["Shuangyu Jaden Cao", "Paul Leslie Green", "Jason Moore"])},
            {"name": "Group 7", "players": create_players(["Zachary Bakanay", "Philip Vandeplassche", "Tyler McCarthy"])},
            {"name": "Group 8", "players": create_players(["Runsheng Vincent Chen", "Allen Shen", "Sam Xu"])},
            {"name": "Group 9", "players": create_players(["Jiazheng (Kent) Wang", "Ryan Nassau", "Lachlan Cherry"])},
            {"name": "Group 10", "players": create_players(["Kai Seshimo", "Krishh Narsey", "Isaac Farmer"])},
            {"name": "Group 11", "players": create_players(["Ryuho Kobayashi", "Mohsen Moogui", "Diwansha Kumaranathunga"])},
            {"name": "Group 12", "players": create_players(["Jin Qi Low", "Janson Tran", "Arohana Rao Katta"])},
            {"name": "Group 13", "players": create_players(["Luke Anderson", "Richard Weaver", "Santosh Deshpande"])},
            {"name": "Group 14", "players": create_players(["Peter Besnard", "Daniel Ng", "Angel De Luis Sanabria"])},
            {"name": "Group 15", "players": create_players(["Seungheon Sean Yoo", "Michael Zeng", "Kotaro Isayama"])},
            {"name": "Group 16", "players": create_players(["Jin Rui Low", "Jiayu Frank Chen", "Yun Wang"])},
            {"name": "Group 17", "players": create_players(["Mark Mulley", "Benjamin Lander", "Kevin Xu"])},
            {"name": "Group 18", "players": create_players(["Yang Sun", "Soma Sakamoto", "Luqman Ihsan-Hess"])}
        ],
        "knockout": [
            {
                "roundName": "Round of 32",
                "matches": [
                    {"p1": "Hayden Green", "s1": "0", "p2": "Winner Group 18", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 11", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 14", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 7", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 6", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 12", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 15", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 3", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 4", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 13", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 16", "s1": "0", "p2": "Winner Group 17", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 8", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 5", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 9", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 10", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Round of 16", "matches": blank_bracket(8)},
            {"roundName": "Quarter Finals", "matches": blank_bracket(4)},
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #2: Women's Open Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Lin Zhu", "Amy Jang", "Yuriko Newcombe", "Yuyang Arianna Zhang", "Nayu Isayama"])},
            {"name": "Group 2", "players": create_players(["Tiffany Lam", "Bethany Wang", "Kaori Mori", "Yih Xuliu", "Clare Liu"])}
        ],
        "knockout": [
            {
                "roundName": "Semi Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Runner-Up Group 2", "s2": "0", "winner": 0},
                    {"p1": "Runner-Up Group 1", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #3: Men's Open Doubles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["David Lu / Naoya Yamamoto", "Alex Glasson / Mukesh Mahendran", "Jeroen Janssen / Neville Adair"])},
            {"name": "Group 2", "players": create_players(["Jin Rui Low / Hayden Green", "Jesse Barnett / Morgan Barnett", "Thomas Donaldson / Nash McMaster"])},
            {"name": "Group 3", "players": create_players(["Zachary Bakanay / Hui Lun Yip", "Benjamin Lander / Jiayu Frank Chen", "Santosh Deshpande / Arohana Rao Katta"])},
            {"name": "Group 4", "players": create_players(["Luke Anderson / Ryuho Kobayashi", "Dongyi Ian Cao / Shuangyu Jaden Cao", "Luke Luca / Matt Cunningham"])}
        ],
        "knockout": [
            {
                "roundName": "Semi Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Winner Group 3", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 4", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #6: Under 1700 Singles",
        "hasGroups": False,
        "hasKnockout": True,
        "groups": [],
        "knockout": [
            {
                "roundName": "Round of 64",
                "matches": [
                    {"p1": "Shanith Jayamaha", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Peter Meek", "s1": "0", "p2": "Kaori Mori", "s2": "0", "winner": 0},
                    {"p1": "Esmatullah Yawari", "s1": "0", "p2": "William Rome McPherson", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Hyeonuk (Henry) Mun", "s2": "0", "winner": 2},
                    {"p1": "Michael Zeng", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "BYE", "s1": "0", "p2": "Janson Tran", "s2": "0", "winner": 2},
                    {"p1": "Muhammad Ihsan-Hess", "s1": "0", "p2": "Loic Thomann", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Kai Seshimo", "s2": "0", "winner": 2},
                    {"p1": "Peter Besnard", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Isaac Farmer", "s1": "0", "p2": "Philip Vandeplassche", "s2": "0", "winner": 0},
                    {"p1": "Pranav Prasad", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "BYE", "s1": "0", "p2": "Ryan Nassau", "s2": "0", "winner": 2},
                    {"p1": "Seungheon Sean Yoo", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Diwansha Kumaranathunga", "s1": "0", "p2": "Tony Kovacs", "s2": "0", "winner": 0},
                    {"p1": "Jeffrey Chen", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "BYE", "s1": "0", "p2": "Runsheng Vincent Chen", "s2": "0", "winner": 2},
                    {"p1": "Tiffany Lam", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Jason Moore", "s1": "0", "p2": "Brayden Kan", "s2": "0", "winner": 0},
                    {"p1": "Tsz Kin Andersen Kwok", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "BYE", "s1": "0", "p2": "Yang Sun", "s2": "0", "winner": 2},
                    {"p1": "Richard Weaver", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Angel De Luis Sanabria", "s1": "0", "p2": "Yuriko Newcombe", "s2": "0", "winner": 0},
                    {"p1": "Rey Lorenzana", "s1": "0", "p2": "Rolans Schroeder", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Jiazheng (Kent) Wang", "s2": "0", "winner": 2},
                    {"p1": "Geoffrey Lamberton", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Tyler McCarthy", "s1": "0", "p2": "Mohsen Moogui", "s2": "0", "winner": 0},
                    {"p1": "Dean Brunsdon", "s1": "0", "p2": "Bandhu Jayamaha", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Amy Jang", "s2": "0", "winner": 2},
                    {"p1": "Mark Mulley", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "John Slattery", "s1": "0", "p2": "Juan Arias", "s2": "0", "winner": 0},
                    {"p1": "Daniel Ng", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "BYE", "s1": "0", "p2": "Seref Bakanay", "s2": "0", "winner": 2}
                ]
            },
            {"roundName": "Round of 32", "matches": blank_bracket(16)},
            {"roundName": "Round of 16", "matches": blank_bracket(8)},
            {"roundName": "Quarter Finals", "matches": blank_bracket(4)},
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #7: Under 1400 Singles",
        "hasGroups": False,
        "hasKnockout": True,
        "groups": [],
        "knockout": [
            {
                "roundName": "Round of 32",
                "matches": [
                    {"p1": "Jesse Barnett", "s1": "0", "p2": "BYE", "s2": "0", "winner": 1},
                    {"p1": "Quang Bui", "s1": "0", "p2": "Bandhu Jayamaha", "s2": "0", "winner": 0},
                    {"p1": "Roland Schroeder", "s1": "0", "p2": "Neville Adair", "s2": "0", "winner": 0},
                    {"p1": "Jeroen Janssen", "s1": "0", "p2": "Stephen Johnstone", "s2": "0", "winner": 0},
                    {"p1": "Dean Brunsdon", "s1": "0", "p2": "Yat Ching Janice Fan", "s2": "0", "winner": 0},
                    {"p1": "Avinash Sivabalan", "s1": "0", "p2": "Brett Halocha", "s2": "0", "winner": 0},
                    {"p1": "Peter Meek", "s1": "0", "p2": "Jully Katherine Pinzon", "s2": "0", "winner": 0},
                    {"p1": "David Gillard", "s1": "0", "p2": "Esmatullah Yawari", "s2": "0", "winner": 0},
                    {"p1": "Rey Lorenzana", "s1": "0", "p2": "Nash McMaster", "s2": "0", "winner": 0},
                    {"p1": "William Rome McPherson", "s1": "0", "p2": "Nathan Stack", "s2": "0", "winner": 0},
                    {"p1": "Gad Gavua", "s1": "0", "p2": "John Slattery", "s2": "0", "winner": 0},
                    {"p1": "John Buzolic", "s1": "0", "p2": "Paul Cheung", "s2": "0", "winner": 0},
                    {"p1": "Dongyi Ian Cao", "s1": "0", "p2": "Tania Parveen", "s2": "0", "winner": 0},
                    {"p1": "Jerry Ho", "s1": "0", "p2": "Morgan Barnett", "s2": "0", "winner": 0},
                    {"p1": "Vivienne Halocha", "s1": "0", "p2": "Loic Thomann", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Tony Kovacs", "s2": "0", "winner": 2}
                ]
            },
            {"roundName": "Round of 16", "matches": blank_bracket(8)},
            {"roundName": "Quarter Finals", "matches": blank_bracket(4)},
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #8: Under 19 Boy's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Soma Sakamoto", "Luqman Ihsan-Hess", "Nash McMaster"])},
            {"name": "Group 2", "players": create_players(["Praveen Gunawardena", "Lachlan Cherry", "Harrison Sy"])},
            {"name": "Group 3", "players": create_players(["Allen Shen", "Cohen McMaster", "Kotaro Isayama", "Ian Simon"])}
        ],
        "knockout": [
            {
                "roundName": "Quarter Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "Runner-Up Group 3", "s1": "0", "p2": "Runner-Up Group 2", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 3", "s1": "0", "p2": "Runner-Up Group 1", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #9: Under 19 Girl's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Bethany Wang", "Yat Ching Janice Fan", "Nayu Isayama"])},
            {"name": "Group 2", "players": create_players(["Kaori Mori", "Eliya Kan", "Gianna Chiu"])}
        ],
        "knockout": [
            {
                "roundName": "Semi Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Runner-Up Group 2", "s2": "0", "winner": 0},
                    {"p1": "Runner-Up Group 1", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #10: Under 17 Boy's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Shuangyu Jaden Cao", "Pranav Prasad", "Luqman Ihsan-Hess"])},
            {"name": "Group 2", "players": create_players(["Seungheon Sean Yoo", "Jin Rui Low", "Brayden Kan", "Ian Simon"])}
        ],
        "knockout": [
            {
                "roundName": "Grand Final",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            }
        ]
    },
    {
        "eventName": "Event #12: Under 15 Boy's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Jin Qi Low", "Isaac Farmer", "William Rome McPherson"])},
            {"name": "Group 2", "players": create_players(["Boris Zhang", "Harrison Sy", "Matias Chiu"])},
            {"name": "Group 3", "players": create_players(["Krishh Narsey", "Avinash Sivabalan", "Dan Kim"])},
            {"name": "Group 4", "players": create_players(["Allen Shen", "Nash McMaster", "Lucas Michael"])},
            {"name": "Group 5", "players": create_players(["Dongyi Ian Cao", "Kasparas Bendoraitis", "Jayden Fan"])},
            {"name": "Group 6", "players": create_players(["Muhammad Ihsan-Hess", "Diwansha Kumaranathunga", "Thomas Donaldson"])},
            {"name": "Group 7", "players": create_players(["Kevin Xu", "Abubakr Ihsan-Hess", "Shae Easterbrook"])}
        ],
        "knockout": [
            {
                "roundName": "Quarter Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 5", "s1": "0", "p2": "Winner Group 4", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 3", "s1": "0", "p2": "Winner Group 6", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 7", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #14: Under 13 Boy's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Krishh Narsey"])},
            {"name": "Group 2", "players": create_players(["Pacer Lu-Muller", "Lucas Michael", "Aiden Jang"])},
            {"name": "Group 3", "players": create_players(["Kevin Xu", "Alexey Shlykov", "Ace Glasson"])},
            {"name": "Group 4", "players": create_players(["Abubakr Ihsan-Hess", "Dzidzor Gavua", "Carlo De Angelis"])},
            {"name": "Group 5", "players": create_players(["Timothy Michael", "Dan Kim", "Alden Shen"])},
            {"name": "Group 6", "players": create_players(["Leeds Rautenberg", "Lim Liu", "Samuel Elias"])},
            {"name": "Group 7", "players": create_players(["Matias Chiu", "Julian Addison Hsu", "Yen-Hsing Wei"])},
            {"name": "Group 8", "players": create_players(["Harold Yu", "Aaryan Uchil", "Mateo Kwong", "Yayra Gavua"])}
        ],
        "knockout": [
            {
                "roundName": "Quarter Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Winner Group 5", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 7", "s1": "0", "p2": "Winner Group 4", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 3", "s1": "0", "p2": "Winner Group 8", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 6", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #15: Under 13 Girl's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Yat Ching Janice Fan", "Maryam Deen", "Sahana Dinesh"])},
            {"name": "Group 2", "players": create_players(["Yuyang Arianna Zhang", "Yih Xuliu", "Yuana Dawes"])},
            {"name": "Group 3", "players": create_players(["Eliya Kan", "Zhimo Chloe Wu", "Yuliana Hei", "Jingyi Hannah Hu"])}
        ],
        "knockout": [
            {
                "roundName": "Semi Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 3", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #16: Under 11 Boy's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Pacer Lu-Muller"])},
            {"name": "Group 2", "players": create_players(["Timothy Michael", "Alexey Shlykov", "Aiden Jang"])},
            {"name": "Group 3", "players": create_players(["Harold Yu", "Sera Akema", "Samuel Elias"])},
            {"name": "Group 4", "players": create_players(["Lim Liu", "Yayra Gavua", "Alden Shen"])},
            {"name": "Group 5", "players": create_players(["Aaryan Uchil", "Mateo Kwong", "Ace Glasson"])},
            {"name": "Group 6", "players": create_players(["Dzidzor Gavua", "Lucas L Zhao", "Yen-Hsing Wei", "Alan Wang"])}
        ],
        "knockout": [
            {
                "roundName": "Quarter Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "Winner Group 6", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 3", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 4", "s1": "0", "p2": "Winner Group 5", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Semi Finals", "matches": blank_bracket(2)},
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    },
    {
        "eventName": "Event #17: Under 11 Girl's Singles",
        "hasGroups": True,
        "hasKnockout": True,
        "groups": [
            {"name": "Group 1", "players": create_players(["Yuyang Arianna Zhang", "Yuliana Hei"])},
            {"name": "Group 2", "players": create_players(["Zhimo Chloe Wu", "Sahana Dinesh", "Bella Mehra"])},
            {"name": "Group 3", "players": create_players(["Maryam Deen", "Yuana Dawes", "Jingyi Hannah Hu"])}
        ],
        "knockout": [
            {
                "roundName": "Semi Finals",
                "matches": [
                    {"p1": "Winner Group 1", "s1": "0", "p2": "BYE", "s2": "0", "winner": 0},
                    {"p1": "Runner-Up Group 3", "s1": "0", "p2": "Runner-Up Group 2", "s2": "0", "winner": 0},
                    {"p1": "Winner Group 3", "s1": "0", "p2": "Runner-Up Group 1", "s2": "0", "winner": 0},
                    {"p1": "BYE", "s1": "0", "p2": "Winner Group 2", "s2": "0", "winner": 0}
                ]
            },
            {"roundName": "Grand Final", "matches": blank_bracket(1)}
        ]
    }
]

# Push to Firestore
batch = db.batch()
draws_ref = db.collection('draws')

for draw in draws_data:
    # Hash the event name to create the document ID (matches your server logic)
    doc_id = hashlib.md5(draw["eventName"].encode()).hexdigest()[:8]
    
    # Check if we have an explicit ID in your catalog (e.g. "1" for Event #1)
    event_num_match = draw["eventName"].split(":")[0].replace("Event #", "")
    if event_num_match.isdigit():
        doc_id = event_num_match

    draw["id"] = doc_id
    doc_ref = draws_ref.document(doc_id)
    batch.set(doc_ref, draw)

batch.commit()
print("✅ Successfully seeded all Saturday draws into Firebase!")