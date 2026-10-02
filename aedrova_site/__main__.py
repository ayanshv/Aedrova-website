import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "aedrova_site.app:create_app", factory=True, host="127.0.0.1", port=8090, access_log=False
    )
