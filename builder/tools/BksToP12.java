import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.security.Key;
import java.security.KeyStore;
import java.security.Security;
import java.security.cert.Certificate;
import java.util.Collections;
import java.util.Enumeration;

/**
 * BKS -> PKCS12 转换器。
 *
 * 原因：LSPatch 的 KeystoreSpec 用 KeyStore.getDefaultType() 打开 keystore，
 * JDK 21 上默认类型是 PKCS12，直接喂 BKS 会报 "not a PKCS12 keystore"。
 * BKS 又需要 BouncyCastle provider 才能读，所以这里显式指定。
 *
 * 用法：java -cp bcprov.jar:. BksToP12 <bks> <bks密码> <别名> <目标p12> <p12密码>
 */
public final class BksToP12 {

    public static void main(String[] args) throws Exception {
        if (args.length < 5) {
            System.err.println("usage: BksToP12 <src.bks> <srcPass> <alias> <dst.p12> <dstPass>");
            System.exit(2);
        }
        String srcPath = args[0];
        char[] srcPass = args[1].toCharArray();
        String alias = args[2];
        String dstPath = args[3];
        char[] dstPass = args[4].toCharArray();

        Security.addProvider(new org.bouncycastle.jce.provider.BouncyCastleProvider());
        KeyStore src = KeyStore.getInstance("BKS", "BC");
        try (InputStream in = new FileInputStream(srcPath)) {
            src.load(in, srcPass);
        }

        String picked = alias;
        if (picked == null || picked.isEmpty()) {
            picked = Collections.list(src.aliases()).stream().findFirst()
                    .orElseThrow(() -> new IllegalStateException("keystore 里没有任何条目"));
            System.err.println("warn: 未指定别名，自动选择 " + picked);
        }
        if (!src.containsAlias(picked)) {
            System.err.println("可用别名: " + Collections.list(src.aliases()));
            throw new IllegalStateException("别名不存在: " + picked);
        }

        Key key = src.getKey(picked, srcPass);
        Certificate[] chain = src.getCertificateChain(picked);

        KeyStore dst = KeyStore.getInstance("PKCS12");
        dst.load(null, null);
        dst.setKeyEntry(picked, key, dstPass, chain);
        try (OutputStream out = new FileOutputStream(dstPath)) {
            dst.store(out, dstPass);
        }

        try (InputStream in = new FileInputStream(dstPath)) {
            KeyStore check = KeyStore.getInstance("PKCS12");
            check.load(in, dstPass);
            Enumeration<String> e = check.aliases();
            System.out.println("ok: " + dstPath + " alias=" + picked + " entries="
                    + Collections.list(e).size());
        }
    }
}
