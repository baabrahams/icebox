import "dotenv/config";
import express from "express";
import smsRouter from "./routes/sms.js";

const app = express();
app.use(express.urlencoded({ extended: false }));
app.use(express.json());

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.use(smsRouter);

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Icebox listening on port ${PORT}`);
});

export default app;
