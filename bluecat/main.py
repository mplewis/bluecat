from fastapi import FastAPI, File, UploadFile


app = FastAPI()


@app.post("/print")
async def print(image: UploadFile = File(...)):
    return {"filename": image.filename}
