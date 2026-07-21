from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.survey import Question, Answer, QuestionType
from app.models.analysis import SentimentResult, Theme, ThemeAssignment

analyzer = SentimentIntensityAnalyzer()

def analyze_sentiment(texts: list[str]):
    results = []
    for text in texts:
        scores = analyzer.polarity_scores(text)
        comp = scores['compound']
        if comp >= 0.05:
            label = "positive"
        elif comp <= -0.05:
            label = "negative"
        else:
            label = "neutral"
        results.append({
            "score": comp,
            "label": label,
            "confidence": abs(comp) if label != "neutral" else 1 - abs(comp)
        })
    return results

def extract_themes(texts: list[str], n_themes=5):
    if len(texts) < n_themes:
        n_themes = max(1, len(texts))
    vectorizer = TfidfVectorizer(max_df=0.95, min_df=2, stop_words='english')
    try:
        tfidf = vectorizer.fit_transform(texts)
    except ValueError:
        return [] 
    nmf_model = NMF(n_components=n_themes, random_state=42)
    nmf_model.fit(tfidf)
    
    feature_names = vectorizer.get_feature_names_out()
    themes = []
    for topic_idx, topic in enumerate(nmf_model.components_):
        top_features_ind = topic.argsort()[:-6:-1]
        top_features = [feature_names[i] for i in top_features_ind]
        themes.append({
            "name": f"Theme {topic_idx+1}: {', '.join(top_features[:2])}",
            "keywords": top_features,
            "response_count": 0,
            "avg_sentiment": 0.0
        })
    return themes

async def run_full_analysis(db: AsyncSession, survey_id: int):
    result = await db.execute(
        select(Answer.id, Answer.value_text)
        .join(Question, Question.id == Answer.question_id)
        .where(Question.survey_id == survey_id, Question.question_type == QuestionType.open_text, Answer.value_text.isnot(None))
    )
    answers = result.all()
    if not answers:
        return
        
    texts = [a.value_text for a in answers]
    ids = [a.id for a in answers]
    
    sentiments = analyze_sentiment(texts)
    for ans_id, sent in zip(ids, sentiments):
        sr = SentimentResult(
            answer_id=ans_id,
            score=sent["score"],
            label=sent["label"],
            confidence=sent["confidence"],
            model_used="vader"
        )
        db.add(sr)
        
    themes = extract_themes(texts)
    for t in themes:
        theme_obj = Theme(
            survey_id=survey_id,
            name=t["name"],
            keywords=t["keywords"],
            response_count=0,
            avg_sentiment=0.0
        )
        db.add(theme_obj)
    
    await db.commit()
