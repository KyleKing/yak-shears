import SwiftUI
import YakShearsKit

/// Sign in to a Yak Shears server to start syncing.
struct SignInView: View {
    @Environment(Account.self) private var account
    @Environment(\.dismiss) private var dismiss
    @State private var server = Account.defaultServer.absoluteString
    @State private var email = ""
    @State private var password = ""
    @State private var error: String?
    @State private var isSigningIn = false

    let onSignedIn: () -> Void

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Server", text: $server)
                        .textContentType(.URL)
                        .autocorrectionDisabled()
                    TextField("Email", text: $email)
                        .textContentType(.username)
                        .autocorrectionDisabled()
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                        .onSubmit(signIn)
                } footer: {
                    if let error {
                        Text(error).foregroundStyle(.red)
                    }
                }
            }
            #if os(iOS)
            .textInputAutocapitalization(.never)
            #endif
            .navigationTitle("Sign In")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isSigningIn {
                        ProgressView()
                    } else {
                        Button("Sign In", action: signIn)
                            .disabled(email.isEmpty || password.isEmpty || URL(string: server) == nil)
                    }
                }
            }
        }
    }

    private func signIn() {
        guard let url = URL(string: server.trimmingCharacters(in: .whitespaces)) else { return }
        isSigningIn = true
        Task {
            defer { isSigningIn = false }
            do {
                try await account.signIn(server: url, email: email, password: password)
                onSignedIn()
                dismiss()
            } catch SyncError.server(_, let message) {
                error = message
            } catch SyncError.unauthorized {
                error = "Invalid email or password"
            } catch {
                self.error = error.localizedDescription
            }
        }
    }
}
