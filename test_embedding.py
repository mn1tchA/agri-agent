import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings

os.environ["GOOGLE_API_KEY"] = "AIzaSyDwid6-YB_HPWTAdy5IyArko5zNEVFGt0M"

try:
    print("Testing text-embedding-004...")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    res = embeddings.embed_query("test")
    print("models/text-embedding-004 succeeded!")
except Exception as e:
    print("models/text-embedding-004 failed:", e)

try:
    print("Testing text-embedding-004 without models/ prefix...")
    embeddings = GoogleGenerativeAIEmbeddings(model="text-embedding-004")
    res = embeddings.embed_query("test")
    print("text-embedding-004 succeeded!")
except Exception as e:
    print("text-embedding-004 failed:", e)
