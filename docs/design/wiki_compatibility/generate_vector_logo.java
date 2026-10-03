import java.awt.*;
import java.awt.geom.*;
import java.awt.image.BufferedImage;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
import javax.imageio.ImageIO;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.*;

/** Прототип для Wiki: преобразование известного знака в простые залитые контуры. */
class GenerateVectorLogo {
    static final StringBuilder paths = new StringBuilder();
    static final double DX = 19, DY = 25;
    static Graphics2D preview;
    static int count;

    static String num(double n) {
        return String.format(Locale.ROOT, "%.5f", n).replaceAll("0+$", "").replaceAll("\\.$", "");
    }

    static void emit(Shape shape, String color) {
        preview.setColor(Color.decode(color));
        preview.fill(shape);
        AffineTransform scale = AffineTransform.getScaleInstance(48.0/128, 48.0/128);
        PathIterator it = shape.getPathIterator(scale);
        double[] p = new double[6];
        StringBuilder d = new StringBuilder();
        while (!it.isDone()) {
            int type = it.currentSegment(p);
            char cmd = "MLQCZ".charAt(type);
            int length = new int[]{2, 2, 4, 6, 0}[type];
            d.append(cmd);
            for (int i=0; i<length; i++) d.append(i==0 ? "" : " ").append(num(p[i]));
            it.next();
        }
        paths.append("<path fill=\"").append(color).append("\" d=\"").append(d).append("\"/>\n");
        count++;
    }

    // Исходник использует абсолютные M/L/H/V/C/S/Q/Z; неизвестное отклоняется.
    static Path2D parse(String d) {
        Matcher m = Pattern.compile("[A-Za-z]|[-+]?(?:\\d*\\.\\d+|\\d+)(?:[eE][-+]?\\d+)?").matcher(d);
        ArrayList<String> tokens = new ArrayList<>();
        while (m.find()) tokens.add(m.group());
        Path2D.Double p = new Path2D.Double();
        int i=0;
        double x=0,y=0,cx=0,cy=0,sx=0,sy=0;
        char last=' ';
        while (i<tokens.size()) {
            char cmd=tokens.get(i++).charAt(0);
            int len=switch(cmd) {case 'M','L' -> 2; case 'H','V' -> 1; case 'C' -> 6; case 'S','Q' -> 4; case 'Z' -> 0; default -> throw new IllegalArgumentException("Unsupported: "+cmd);};
            double[] a=new double[len];
            for(int j=0;j<len;j++) a[j]=Double.parseDouble(tokens.get(i++));
            switch(cmd) {
                case 'M': x=a[0];y=a[1];sx=x;sy=y;p.moveTo(x,y);break;
                case 'L': x=a[0];y=a[1];p.lineTo(x,y);break;
                case 'H': x=a[0];p.lineTo(x,y);break;
                case 'V': y=a[0];p.lineTo(x,y);break;
                case 'C': p.curveTo(a[0],a[1],a[2],a[3],a[4],a[5]);cx=a[2];cy=a[3];x=a[4];y=a[5];break;
                case 'S': p.curveTo(last=='C'||last=='S'?2*x-cx:x,last=='C'||last=='S'?2*y-cy:y,a[0],a[1],a[2],a[3]);cx=a[0];cy=a[1];x=a[2];y=a[3];break;
                case 'Q': p.quadTo(a[0],a[1],a[2],a[3]);x=a[2];y=a[3];break;
                case 'Z': p.closePath();x=sx;y=sy;break;
            }
            last=cmd;
        }
        return p;
    }

    static void paint(Shape shape, String color, AffineTransform tr) {
        if(!color.startsWith("url(")) {
            emit(tr.createTransformedShape(shape),color);
            return;
        }
        if(!color.equals("url(#route-ruleway-icon)")) throw new IllegalArgumentException(color);
        emit(tr.createTransformedShape(shape),"#142D3B");
        // Перекрывающиеся полуплоскости сохраняют непрозрачность и не дают швов.
        for(int i=1;i<=64;i++) {
            double t=i/64.0, x=41+t*DX,y=64+t*DY;
            Path2D band = new Path2D.Double();
            band.moveTo(x-100*DY,y+100*DX);
            band.lineTo(x+100*DY,y-100*DX);
            band.lineTo(x+100*DY+100*DX,y-100*DX+100*DY);
            band.lineTo(x-100*DY+100*DX,y+100*DX+100*DY);
            band.closePath();
            Area area=new Area(shape);area.intersect(new Area(band));
            if(area.isEmpty()) continue;
            String shade=String.format("#%02X%02X%02X",Math.round(20+(8-20)*t),Math.round(45+(127-45)*t),Math.round(59+(116-59)*t));
            emit(tr.createTransformedShape(area),shade);
        }
    }

    static void visit(Element e, AffineTransform parent) {
        AffineTransform tr=new AffineTransform(parent);
        if(e.hasAttribute("transform")) {
            Matcher m=Pattern.compile("translate\\(([-.0-9]+) ([-.0-9]+)\\)").matcher(e.getAttribute("transform"));
            if(!m.matches()) throw new IllegalArgumentException(e.getAttribute("transform"));
            tr.translate(Double.parseDouble(m.group(1)),Double.parseDouble(m.group(2)));
        }
        Shape shape=null;
        switch(e.getTagName()) {
            case "title", "desc", "defs": return;
            case "svg", "g": break;
            case "path": shape=parse(e.getAttribute("d"));break;
            case "rect":
                double x=Double.parseDouble(e.getAttribute("x")),y=Double.parseDouble(e.getAttribute("y")),w=Double.parseDouble(e.getAttribute("width")),h=Double.parseDouble(e.getAttribute("height")),r=Double.parseDouble(e.getAttribute("rx"));
                shape=new RoundRectangle2D.Double(x,y,w,h,r*2,r*2);break;
            default: throw new IllegalArgumentException(e.getTagName());
        }
        if(shape!=null) {
            String fill=e.getAttribute("fill");
            if(!fill.equals("none")) paint(shape,fill.isEmpty()?"#000000":fill,tr);
            if(e.hasAttribute("stroke")) {
                if(!e.getAttribute("stroke-linecap").equals("round")) throw new IllegalArgumentException("cap");
                float width=Float.parseFloat(e.getAttribute("stroke-width"));
                Shape outline=new BasicStroke(width,BasicStroke.CAP_ROUND,BasicStroke.JOIN_ROUND).createStrokedShape(shape);
                paint(outline,e.getAttribute("stroke"),tr);
            }
        }
        for(Node child=e.getFirstChild();child!=null;child=child.getNextSibling()) if(child instanceof Element) visit((Element)child,tr);
    }

    public static void main(String[] args) throws Exception {
        if (!Files.exists(Path.of("/.dockerenv"))) throw new IllegalStateException("Запускайте в Docker");
        String hash=HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(Path.of(args[0]))));
        if (!hash.equals("87e0a39a5e0ba8f20d2cc68b3e40e3582bdfef28204044675b05dd4b3959f462"))
            throw new IllegalArgumentException("Исходный знак изменён: проверьте геометрию и параметры градиента перед преобразованием");
        Path out=Path.of(args[1]);Files.createDirectories(out);
        BufferedImage png=new BufferedImage(512,512,BufferedImage.TYPE_INT_ARGB);
        preview=png.createGraphics();preview.setRenderingHint(RenderingHints.KEY_ANTIALIASING,RenderingHints.VALUE_ANTIALIAS_ON);preview.scale(4,4);
        var factory=DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        Document doc=factory.newDocumentBuilder().parse(Path.of(args[0]).toFile());
        visit(doc.getDocumentElement(),new AffineTransform());preview.dispose();
        String svg="<svg width=\"48\" height=\"48\" viewBox=\"0 0 48 48\">\n"+paths+"</svg>";
        Files.writeString(out.resolve("ruleway_vector_logo.iuml"),"' Векторный знак 48 × 48 из docs/ruleway_design/ruleway-icon.svg.\n' Градиент приближён 64 переходами цвета; порядок обновления — docs/context.md.\n' SHA-256 исходника: "+hash+"\n!ifndef ruleway_logo_loaded\n!define ruleway_logo_loaded\nsprite ruleway_logo "+svg+"\n!endif\n");
        Files.writeString(out.resolve("ruleway_vector_logo.svg"),svg.replace("<svg ","<svg xmlns=\"http://www.w3.org/2000/svg\" "));
        ImageIO.write(png,"png",out.resolve("geometry_reference.png").toFile());
        System.out.println("paths="+count+" bytes="+svg.length());
    }
}
