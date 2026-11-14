
const loginForm = document.getElementById("loginForm");
const registerForm = document.getElementById("registerForm");


// Login form - temporary demonstration
if (loginForm) {

    loginForm.addEventListener("submit", function(event) {

        event.preventDefault();

        alert(
            "Login page is working. Database authentication will be connected in the next stage."
        );

    });

}


// Registration form - temporary demonstration
if (registerForm) {

    registerForm.addEventListener("submit", function(event) {

        event.preventDefault();

        const password =
            document.getElementById("password").value;

        const confirmPassword =
            document.getElementById("confirmPassword").value;


        if (password !== confirmPassword) {

            alert("Passwords do not match!");

            return;

        }


        if (password.length < 8) {

            alert("Password must contain at least 8 characters.");

            return;

        }


        alert(
            "Registration page is working. Database registration will be connected in the next stage."
        );

    });

}
