"""
Landing Page Builder — Gemini chat service for generating HTML landing pages.
"""


def landing_page_chat(
    user_message: str,
    conversation_history: list = None,
    current_html: str = ""
) -> dict:
    import os
    import sys
    import ssl
    import certifi

    # SSL fix (same as video_planner_chat)
    if 'HTTPLIB2_CA_CERTS' in os.environ:
        del os.environ['HTTPLIB2_CA_CERTS']
    os.environ['HTTPLIB2_CA_CERTS'] = certifi.where()
    ssl._create_default_https_context = ssl._create_unverified_context

    import google.generativeai as genai

    if not user_message or not user_message.strip():
        return {"success": False, "html": current_html, "ai_message": "", "error": "No message provided"}

    if conversation_history is None:
        conversation_history = []
    conversation_history = conversation_history[-15:]

    system_prompt = """אתה מעצב אתרים מקצועי שבונה דפי נחיתה מדהימים.
תפקידך לעזור למשתמש לבנות דף נחיתה יפה ומקצועי לפי הבקשה שלו.

חוקים:
1. כל תשובה חייבת לכלול שני חלקים:
   - הסבר קצר בעברית על מה שעשית/שיניתי
   - בלוק קוד HTML מלא בתוך ```html ... ```
2. ה-HTML חייב להיות דף שלם עם <!DOCTYPE html>, <head>, <body>
3. הדף חייב להיות RTL עם כיוון עברי
4. השתמש ב-Google Fonts (Heebo) לטיפוגרפיה עברית
5. הדף חייב להיות רספונסיבי (mobile-friendly)
6. כל ה-CSS חייב להיות inline בתוך תגית <style> - קובץ אחד בלבד
7. עיצוב מודרני ומקצועי עם גרדיאנטים, צללים, ואנימציות עדינות
8. בכל עריכה - החזר את הדף המלא, לא רק את החלק שהשתנה
9. אם המשתמש מבקש שינוי צבע/טקסט/מבנה - שנה בדף הקיים ותחזיר את כולו"""

    try:
        genai.configure(transport='rest')

        model = genai.GenerativeModel(
            model_name='gemini-2.0-flash',
            system_instruction=system_prompt
        )

        history_for_gemini = []
        for msg in conversation_history:
            role = "user" if msg.get("role") == "user" else "model"
            history_for_gemini.append({"role": role, "parts": [msg.get("content", "")]})

        chat = model.start_chat(history=history_for_gemini)

        full_input = user_message
        if current_html and current_html.strip():
            full_input = f"הדף הנוכחי:\n```html\n{current_html}\n```\n\nבקשת המשתמש: {user_message}"

        response = chat.send_message(full_input)
        response_text = response.text.strip()

        # Parse: extract AI message and HTML separately
        ai_message = ""
        html = ""

        if "```html" in response_text:
            parts = response_text.split("```html", 1)
            ai_message = parts[0].strip()
            html_part = parts[1]
            # Remove closing ```
            if "```" in html_part:
                html = html_part.split("```", 1)[0].strip()
            else:
                html = html_part.strip()
        else:
            ai_message = response_text
            html = ""

        return {
            "success": True,
            "html": html if html else current_html,
            "ai_message": ai_message if ai_message else "הנה הדף שלך!"
        }

    except Exception as e:
        print(f"[Landing] Error: {str(e)}")
        return {
            "success": False,
            "html": current_html,
            "ai_message": "שגיאה טכנית בחיבור. נסה שנית.",
            "error": str(e)
        }
