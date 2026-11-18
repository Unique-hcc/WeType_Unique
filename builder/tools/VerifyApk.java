import com.android.apksig.ApkVerifier;

import java.io.File;
import java.security.MessageDigest;
import java.security.cert.X509Certificate;
import java.util.List;

/**
 * 用 LSPatch jar 自带的 apksig 校验产物签名。
 *
 * 为什么不用 keytool -printcert -jarfile：LSPatch 只做 v2/v3 签名（不做 v1），
 * keytool 只认 v1 JAR 签名，会直接报 "Not a signed jar file"。
 *
 * 用法：java -cp "lspatch.jar:tools/build" VerifyApk <apk> [期望的证书SHA256(十六进制，可带冒号)]
 * 期望值可用 keytool -exportcert 取出来对比；不一致时退出码为 1。
 */
public final class VerifyApk {

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: VerifyApk <apk> [expectedCertSha256]");
            System.exit(2);
        }
        ApkVerifier.Result r = new ApkVerifier.Builder(new File(args[0])).build().verify();
        System.out.println("verified=" + r.isVerified()
                + " v1=" + r.isVerifiedUsingV1Scheme()
                + " v2=" + r.isVerifiedUsingV2Scheme()
                + " v3=" + r.isVerifiedUsingV3Scheme());
        if (!r.getErrors().isEmpty()) {
            System.out.println("errors=" + r.getErrors());
        }
        if (!r.isVerified()) {
            System.exit(1);
        }

        List<X509Certificate> certs = r.getSignerCertificates();
        if (certs.isEmpty()) {
            System.out.println("no signer certificates");
            System.exit(1);
        }

        String expected = args.length > 1 && args[1] != null
                ? args[1].replace(":", "").replace(" ", "").toUpperCase()
                : "";
        boolean allMatch = true;
        for (X509Certificate c : certs) {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            StringBuilder sb = new StringBuilder();
            for (byte b : md.digest(c.getEncoded())) {
                sb.append(String.format("%02X", b));
            }
            String fp = sb.toString();
            System.out.println("signer subject=" + c.getSubjectX500Principal().getName());
            System.out.println("signer sha256=" + fp);
            if (!expected.isEmpty() && !expected.equals(fp)) {
                System.out.println("MISMATCH: 期望 " + expected);
                allMatch = false;
            }
        }
        if (!expected.isEmpty()) {
            System.out.println(allMatch ? "certificate ok" : "certificate mismatch");
            if (!allMatch) System.exit(1);
        }
    }
}
