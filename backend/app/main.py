from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Algeo-Verify backend is running"}
