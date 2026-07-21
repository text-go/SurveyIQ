import os
import pandas as pd
import random
from datetime import datetime, timedelta

def get_random_date(start, end):
    return start + timedelta(days=random.randint(0, int((end - start).days)))

start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 12, 31)

def generate_nps():
    data = []
    departments = ["Engineering", "Sales", "Marketing", "Product", "HR", "Finance"]
    roles = ["Junior", "Mid", "Senior", "Lead", "Manager", "Director"]
    promoter_reasons = ["Love the new features!", "Very fast and reliable.", "Great support team.", "Easy to use and intuitive."]
    passive_reasons = ["It's okay, does the job.", "Good, but could be faster.", "Missing some features.", "Satisfactory overall."]
    detractor_reasons = ["Too many bugs.", "Support is very slow.", "Crashes frequently.", "Too expensive for what it is."]

    for i in range(500):
        rand = random.random()
        if rand < 0.15:
            score = random.randint(0, 6)
            reason = random.choice(detractor_reasons)
        elif rand < 0.40:
            score = random.randint(7, 8)
            reason = random.choice(passive_reasons)
        else:
            score = random.randint(9, 10)
            reason = random.choice(promoter_reasons)

        data.append({
            "respondent_id": f"R_{i:04d}",
            "date": get_random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "nps_score": score,
            "reason": reason,
            "department": random.choice(departments),
            "role_level": random.choice(roles)
        })
    pd.DataFrame(data).to_csv("nps_survey.csv", index=False)

def generate_employee_engagement():
    data = []
    departments = ["Engineering", "Sales", "Marketing", "Product", "HR", "Finance"]
    for i in range(300):
        sat = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.1, 0.2, 0.4, 0.25])[0]
        wlb = min(5, max(1, sat + random.randint(-1, 1)))
        mgmt = min(5, max(1, sat + random.randint(-1, 1)))
        growth = min(5, max(1, sat + random.randint(-1, 1)))
        
        if sat >= 4:
            feedback = random.choice(["Great place to work", "Love my team", "Good benefits"])
        elif sat == 3:
            feedback = random.choice(["It's alright", "Needs better communication", "Average experience"])
        else:
            feedback = random.choice(["Overworked", "Poor management", "No growth opportunities"])

        data.append({
            "respondent_id": f"EE_{i:04d}",
            "date": get_random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "satisfaction": sat,
            "work_life_balance": wlb,
            "management": mgmt,
            "growth_opportunities": growth,
            "open_feedback": feedback,
            "department": random.choice(departments),
            "tenure_years": round(random.uniform(0.5, 10.0), 1)
        })
    pd.DataFrame(data).to_csv("employee_engagement.csv", index=False)

def generate_customer_satisfaction():
    data = []
    categories = ["Electronics", "Software", "Home", "Fashion"]
    regions = ["North America", "Europe", "Asia Pacific", "Latin America"]
    
    for i in range(400):
        sat = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.1, 0.2, 0.3, 0.3])[0]
        would_rec = "yes" if sat >= 3 else "no"
        sugg = "Make it cheaper" if sat < 3 else "Keep up the good work"

        data.append({
            "respondent_id": f"CS_{i:04d}",
            "date": get_random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "overall_satisfaction": sat,
            "product_quality": min(5, max(1, sat + random.randint(-1, 1))),
            "customer_service": min(5, max(1, sat + random.randint(-1, 1))),
            "would_recommend": would_rec,
            "improvement_suggestions": sugg,
            "product_category": random.choice(categories),
            "region": random.choice(regions)
        })
    pd.DataFrame(data).to_csv("customer_satisfaction.csv", index=False)

def generate_event_feedback():
    data = []
    event_types = ["Conference", "Workshop", "Webinar", "Training"]
    
    for i in range(200):
        rating = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.05, 0.1, 0.4, 0.4])[0]
        attend_again = "yes" if rating >= 4 else "no"

        data.append({
            "respondent_id": f"EV_{i:04d}",
            "event_date": get_random_date(start_date, end_date).strftime("%Y-%m-%d"),
            "overall_rating": rating,
            "speaker_rating": min(5, max(1, rating + random.randint(-1, 1))),
            "venue_rating": min(5, max(1, rating + random.randint(-1, 1))),
            "most_valuable": random.choice(["Networking", "Keynote", "Q&A session"]),
            "least_valuable": random.choice(["Food", "Venue location", "Long breaks"]),
            "attend_again": attend_again,
            "event_type": random.choice(event_types)
        })
    pd.DataFrame(data).to_csv("event_feedback.csv", index=False)

if __name__ == "__main__":
    generate_nps()
    generate_employee_engagement()
    generate_customer_satisfaction()
    generate_event_feedback()
    print("Generated 4 CSV files successfully.")
