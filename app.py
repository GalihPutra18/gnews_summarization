from flask import Flask, request, redirect, url_for, flash, render_template_string
import requests
import re
from bs4 import BeautifulSoup
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from googletrans import Translator
import nltk

# Inisialisasi aplikasi Flask
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Ganti dengan secret key Anda

# Inisialisasi stop words untuk beberapa bahasa
stop_words = {
    'en': set(stopwords.words('english')).union({'said', 'will', 'also', 'one', 'new', 'make'}),
    'id': set(stopwords.words('indonesian')).union({'dan', 'yang', 'di', 'dari', 'pada', 'untuk', 'dengan', 'ke', 'dalam', 'adalah'}),
    'es': set(stopwords.words('spanish')).union({'y', 'el', 'en', 'con', 'para', 'de'}),
    'fr': set(stopwords.words('french')).union({'et', 'le', 'est', 'dans', 'sur', 'avec'})
}

# Fungsi untuk mengambil artikel
def fetch_article(url):
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        title = soup.title.string if soup.title else 'No Title Found'
        paragraphs = soup.find_all('p')
        article = ' '.join([para.get_text() for para in paragraphs])

        # Membersihkan artikel dari iklan
        ad_patterns = re.compile(r"(Advertisement|Scroll to Continue|Baca Juga|Lanjutkan dengan Konten)", re.IGNORECASE)
        article_cleaned = ad_patterns.sub('', article)
        
        return title, article_cleaned.strip()
    else:
        return None, None

# Fungsi untuk meringkas artikel
def summarize_article_flexible(article, num_clusters=2):
    sentences = sent_tokenize(article)
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(sentences)
    kmeans = KMeans(n_clusters=num_clusters, n_init=10)
    kmeans.fit(X)

    point_summary = []
    for i in range(num_clusters):
        cluster_sentences = [sentences[j] for j in range(len(sentences)) if kmeans.labels_[j] == i]
        if cluster_sentences:
            point_summary.append(max(cluster_sentences, key=len))  # Kalimat terpanjang sebagai poin kunci

    paragraph_summary = ' '.join(point_summary)
    return point_summary, paragraph_summary

# Fungsi untuk menghasilkan ringkasan panjang
def long_summary(article):
    sentences = sent_tokenize(article)
    return ' '.join(sentences)

# Fungsi untuk menerjemahkan artikel
def translate_article(article, dest_language='en'):
    translator = Translator()
    try:
        detected_lang = translator.detect(article).lang
        if detected_lang != dest_language:
            translated = translator.translate(article, dest=dest_language)
            return translated.text
        else:
            return article
    except Exception as e:
        return None

# Fungsi untuk menghasilkan hashtag
def generate_hashtags(title, content, lang='en', num_hashtags=5):
    stop_words_set = stop_words.get(lang, set())
    title_words = [word for word in word_tokenize(title.lower()) if word.isalnum() and len(word) > 3 and word not in stop_words_set]
    content_words = [word for word in word_tokenize(content.lower()) if word.isalnum() and len(word) > 3 and word not in stop_words_set]
    
    keywords = title_words * 2 + content_words  # Menggandakan kata judul untuk meningkatkan bobotnya
    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform([' '.join(keywords)])
    
    tfidf_scores = X.toarray().flatten()
    feature_names = vectorizer.get_feature_names_out()
    scored_keywords = sorted(zip(feature_names, tfidf_scores), key=lambda x: x[1], reverse=True)
    
    top_keywords = [f"#{keyword.capitalize()}" for keyword, score in scored_keywords[:num_hashtags]]
    return top_keywords

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form['url']
        lang = request.form['language']
        
        title, article = fetch_article(url)
        if article:
            translated_title = translate_article(title, lang)
            translated_article = translate_article(article, lang)
            num_clusters = int(request.form['num_clusters'])
            point_summary, paragraph_summary = summarize_article_flexible(translated_article, num_clusters)
            long_summary_text = long_summary(translated_article)  # Generate long summary
            hashtags = generate_hashtags(translated_title, translated_article, lang)

            return render_template_string('''  
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>News Summarization App</title>
                    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
                    <style>
                        body {
                            font-family: 'Roboto', sans-serif;
                            background-color: #f4f4f4;
                            margin: 0;
                            padding: 0;
                        }
                        .container {
                            max-width: 800px;
                            margin: 50px auto;
                            padding: 20px;
                            background: white;
                            border-radius: 5px;
                            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                        }
                        h1 {
                            text-align: center;
                            color: #333;
                        }
                        label {
                            margin-top: 10px;
                            display: block;
                        }
                        textarea, input, select, button {
                            width: 100%;
                            padding: 10px;
                            margin-top: 5px;
                            border: 1px solid #ddd;
                            border-radius: 5px;
                        }
                        button {
                            background-color: #28a745;
                            color: white;
                            border: none;
                            cursor: pointer;
                        }
                        button:hover {
                            background-color: #218838;
                        }
                        .summary {
                            margin-top: 20px;
                        }
                        .hashtag {
                            font-weight: bold;
                            color: #28a745;
                        }
                        .error {
                            color: red;
                        }
                        p {
                            font-size: 15px; /* Ukuran teks untuk ringkasan di kecilkan */
                        }
                    </style>
                </head>
                <body>

                <div class="container">
                    <h1>News Summarization & Hashtag Generator</h1>
                    
                    <form method="POST">
                        <label for="url">Enter Article URL:</label>
                        <textarea id="url" name="url" required placeholder="Paste the article URL here..."></textarea>

                        <label for="language">Select Language for Translation:</label>
                        <select id="language" name="language">
                            <option value="en">English</option>
                            <option value="id">Indonesian</option>
                            <option value="es">Spanish</option>
                            <option value="fr">French</option>
                        </select>

                        <label for="num_clusters">Number of Clusters:</label>
                        <input type="number" id="num_clusters" name="num_clusters" min="1" max="5" value="2">

                        <button type="submit">Summarize</button>
                    </form>

                    {% if title %}
                        <div class="summary">
                            <h2>Article Title: {{ title }}</h2>
                            <h3>Key Points:</h3>
                            <ul>
                                {% for point in summary %}
                                    <li>{{ point }}</li>
                                {% endfor %}
                            </ul>

                            <h3>Short Summary:</h3>
                            <p>{{ paragraph_summary }}</p>

                            <h3>Long Summary:</h3>
                            <p>{{ long_summary_text }}</p>

                            <h3>Generated Hashtags:</h3>
                            <p class="hashtag">{{ hashtags | join(', ') }}</p>
                        </div>
                    {% endif %}

                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            <div class="error">
                                <ul>
                                    {% for message in messages %}
                                        <li>{{ message }}</li>
                                    {% endfor %}
                                </ul>
                            </div>
                        {% endif %}
                    {% endwith %}
                </div>

                </body>
                </html>
            ''', title=translated_title, summary=point_summary, paragraph_summary=paragraph_summary, long_summary_text=long_summary_text, hashtags=hashtags)
        else:
            flash('Gagal mengambil artikel. Silakan periksa URL.')
            return redirect(url_for('index'))

    return render_template_string('''  
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>News Summarization App</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Roboto', sans-serif;
                    background-color: #f4f4f4;
                    margin: 0;
                    padding: 0;
                }
                .container {
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background: white;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }
                h1 {
                    text-align: center;
                    color: #333;
                }
                label {
                    margin-top: 10px;
                    display: block;
                }
                textarea, input, select, button {
                    width: 100%;
                    padding: 10px;
                    margin-top: 5px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                }
                button {
                    background-color: #28a745;
                    color: white;
                    border: none;
                    cursor: pointer;
                }
                button:hover {
                    background-color: #218838;
                }
                .summary {
                    margin-top: 20px;
                }
                .hashtag {
                    font-weight: bold;
                    color: #28a745;
                }
                .error {
                    color: red;
                }
            </style>
        </head>
        <body>

        <div class="container">
            <h1>News Summarization & Hashtag Generator</h1>
            
            <form method="POST">
                <label for="url">Enter Article URL:</label>
                <textarea id="url" name="url" required placeholder="Paste the article URL here..."></textarea>

                <label for="language">Select Language for Translation:</label>
                <select id="language" name="language">
                    <option value="en">English</option>
                    <option value="id">Indonesian</option>
                    <option value="es">Spanish</option>
                    <option value="fr">French</option>
                </select>

                <label for="num_clusters">Number of Clusters:</label>
                <input type="number" id="num_clusters" name="num_clusters" min="1" max="5" value="2">

                <button type="submit">Summarize</button>
            </form>
        </div>

        </body>
        </html>
    ''')

if __name__ == '__main__':
    app.run(debug=True)
