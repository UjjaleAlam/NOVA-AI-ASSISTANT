import customtkinter as ctk


class SelectionWidget:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()

        self.root.title("Nova")

        self.root.geometry("650x560")

        self.root.attributes("-topmost", True)

        self.root.protocol("WM_DELETE_WINDOW", self.hide)

        self.root.withdraw()

        self.items = []

        # ---------------- Title ----------------

        self.title_label = ctk.CTkLabel(
            self.root,
            text="",
            font=("Segoe UI", 22, "bold")
        )

        self.title_label.pack(pady=(15, 10))

        # ---------------- Search ----------------

        self.search = ctk.CTkEntry(
            self.root,
            width=560,
            placeholder_text="Search..."
        )

        self.search.pack(pady=(0, 10))

        # ---------------- Results ----------------

        self.textbox = ctk.CTkTextbox(
            self.root,
            width=600,
            height=380,
            font=("Consolas", 15)
        )

        self.textbox.pack()

        # ---------------- Bottom ----------------

        bottom = ctk.CTkFrame(
            self.root,
            fg_color="transparent"
        )

        bottom.pack(fill="x", padx=20, pady=15)

        self.status = ctk.CTkLabel(
            bottom,
            text=""
        )

        self.status.pack(side="left")

        close = ctk.CTkButton(
            bottom,
            text="Close",
            command=self.hide
        )

        close.pack(side="right")

    # ----------------------------------------

    def start(self):

        self.root.mainloop()

    # ----------------------------------------

    def show(self, title, items):

        self.title_label.configure(text=title)

        self.items = items

        self.textbox.configure(state="normal")

        self.textbox.delete("1.0", "end")

        for i, item in enumerate(items, start=1):

            if isinstance(item, dict):

                name = item["name"]

            else:

                name = str(item)

            self.textbox.insert(
                "end",
                f"{i}. {name}\n"
            )

        self.textbox.configure(state="disabled")

        self.status.configure(
            text=f"{len(items)} item(s)"
        )

        self.root.deiconify()

        self.root.lift()

        self.root.focus_force()

    # ----------------------------------------

    def hide(self):

        self.root.withdraw()